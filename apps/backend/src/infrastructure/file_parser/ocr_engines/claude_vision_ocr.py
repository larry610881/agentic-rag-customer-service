"""Claude Vision OCR engine using Anthropic Python SDK.

Prompt 集與影像壓縮已抽到 ``prompts.py`` / ``_image.py``（Issue #78，與
OpenAI 相容視覺引擎共用）；此模組保留舊名稱 re-export 供既有 caller / 測試使用。
"""

from __future__ import annotations

import asyncio
import base64
import time

import anthropic

from src.domain.shared.exceptions import OcrProcessingError
from src.infrastructure.file_parser.ocr_engines._image import (  # noqa: F401
    _MAX_IMAGE_BYTES,
    _compress_image,
)
from src.infrastructure.file_parser.ocr_engines.base import (
    OcrClassifyResult,
    OcrEngine,
    OcrPageResult,
)
from src.infrastructure.file_parser.ocr_engines.prompts import (  # noqa: F401
    _CATALOG_PROMPT,
    _CLASSIFY_PROMPT,
    _COVER_PROMPT,
    _DEFAULT_PROMPT,
    _MIXED_PROMPT,
    _OCR_DISCIPLINE,
    _PAGE_TYPE_PROMPTS,
    _PROMOTION_PROMPT,
    _SLICE_AWARE_PREFIX,
    _VALID_PAGE_TYPES,
    OCR_PROMPTS,
    normalize_page_type,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class ClaudeVisionOcrEngine(OcrEngine):
    """OCR engine that uses Claude Vision API for text extraction."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-haiku-4-5-20251001",
        max_concurrent: int = 5,
        api_key_resolver=None,
    ) -> None:
        self._api_key = api_key
        self._api_key_resolver = api_key_resolver  # async (provider_name) -> str
        self._client: anthropic.AsyncAnthropic | None = None
        if api_key:
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._semaphore = asyncio.Semaphore(max_concurrent)
        # 累計計數器僅為向後相容保留；管線改用 *_with_usage 結果 / OcrUsageTally
        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0

    @property
    def model_spec(self) -> str:
        return f"anthropic:{self._model}"

    async def _ensure_client(self, force: bool = False) -> anthropic.AsyncAnthropic:
        # force=True 強制重新解析 key + 重建 client，用於 auth error retry
        if self._client is not None and not force:
            return self._client
        api_key = self._api_key
        if not api_key and self._api_key_resolver:
            api_key = await self._api_key_resolver("anthropic")
        if not api_key or not api_key.strip():
            # 防禦性：空字串 / 純空白都不能建 client
            # 之前空字串會被當成 truthy（httpx 拒 header）導致整個 worker 後續 OCR 全爆
            raise OcrProcessingError(
                "Claude auth error: Anthropic API key not configured for OCR "
                "(empty or whitespace)"
            )
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        return self._client

    def _image_block(self, image_bytes: bytes) -> tuple[dict, str, float]:
        image_bytes, media_type = _compress_image(image_bytes)
        b64 = base64.standard_b64encode(image_bytes).decode()
        block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
        return block, media_type, len(image_bytes) / 1024

    async def ocr_page_with_usage(
        self, image_bytes: bytes, prompt: str | None = None
    ) -> OcrPageResult:
        prompt = prompt or _DEFAULT_PROMPT
        image_block, media_type, img_kb = self._image_block(image_bytes)
        # 一次 retry：第一次拿到 auth error 時假設 client 帶壞 key，
        # invalidate 後重新解析 key 再試。常見於 worker 啟動時 DB
        # 慢一拍導致首頁 OCR 拿到空 key 緩存的情境。
        for attempt in (0, 1):
            try:
                client = await self._ensure_client(force=attempt == 1)
                async with self._semaphore:
                    t0 = time.perf_counter()
                    message = await client.messages.create(
                        model=self._model,
                        max_tokens=8192,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    image_block,
                                    {"type": "text", "text": prompt},
                                ],
                            }
                        ],
                    )
                elapsed_ms = round((time.perf_counter() - t0) * 1000)
                usage = message.usage
                self.last_input_tokens += usage.input_tokens
                self.last_output_tokens += usage.output_tokens
                logger.info(
                    "ocr.page.done",
                    model=self._model,
                    media_type=media_type,
                    image_kb=round(img_kb),
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    elapsed_ms=elapsed_ms,
                    attempt=attempt,
                )
                return OcrPageResult(
                    text=message.content[0].text,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    model=self.model_spec,
                )
            except anthropic.AuthenticationError as e:
                if attempt == 0:
                    logger.warning(
                        "ocr.auth_error.retry",
                        error=str(e),
                        action="invalidate_client_and_resolve_again",
                    )
                    self._client = None  # 強制下次 _ensure_client 重新解析
                    continue
                raise OcrProcessingError(f"Claude auth error: {e}") from e
            except ValueError as e:
                # httpx 對空 Bearer header 會丟 ValueError("Illegal header value")
                if "Illegal header value" in str(e) and attempt == 0:
                    logger.warning(
                        "ocr.illegal_header.retry",
                        error=str(e),
                        action="invalidate_client_and_resolve_again",
                    )
                    self._client = None
                    continue
                raise OcrProcessingError(f"Claude header error: {e}") from e
            except anthropic.APIError as e:
                raise OcrProcessingError(f"Claude API error: {e}") from e
            except (KeyError, IndexError) as e:
                raise OcrProcessingError(str(e)) from e
        # Unreachable — both attempts must either return or raise
        raise OcrProcessingError("OCR exhausted retries")

    async def classify_page_type_with_usage(
        self, image_bytes: bytes
    ) -> OcrClassifyResult:
        """Detect DM page type for auto-dispatch routing.

        Falls back to ``catalog`` on classification failure（既有預設行為，
        對 84% 商品列表頁不會改變結果）。
        """
        image_block, _media_type, _img_kb = self._image_block(image_bytes)

        for attempt in (0, 1):
            try:
                client = await self._ensure_client(force=attempt == 1)
                async with self._semaphore:
                    message = await client.messages.create(
                        model=self._model,
                        max_tokens=20,  # 單 token 就夠
                        messages=[{
                            "role": "user",
                            "content": [
                                image_block,
                                {"type": "text", "text": _CLASSIFY_PROMPT},
                            ],
                        }],
                    )
                usage = message.usage
                self.last_input_tokens += usage.input_tokens
                self.last_output_tokens += usage.output_tokens
                raw = message.content[0].text.strip().lower()
                page_type = normalize_page_type(raw, fallback="")
                if page_type:
                    logger.info(
                        "ocr.classify.done",
                        page_type=page_type,
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                    )
                else:
                    logger.warning(
                        "ocr.classify.invalid_response",
                        raw=raw[:100],
                        fallback="catalog",
                    )
                    page_type = "catalog"
                return OcrClassifyResult(
                    page_type=page_type,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    model=self.model_spec,
                )
            except anthropic.AuthenticationError as e:
                if attempt == 0:
                    self._client = None
                    continue
                raise OcrProcessingError(f"Claude auth error: {e}") from e
            except ValueError as e:
                if "Illegal header value" in str(e) and attempt == 0:
                    self._client = None
                    continue
                raise OcrProcessingError(f"Claude header error: {e}") from e
            except anthropic.APIError as e:
                # Classification 失敗不應卡住 OCR — fallback catalog 跟舊行為一致
                logger.warning(
                    "ocr.classify.api_error",
                    error=str(e)[:200],
                    fallback="catalog",
                )
                return OcrClassifyResult(page_type="catalog", model=self.model_spec)
        raise OcrProcessingError("classify_page_type exhausted retries")
