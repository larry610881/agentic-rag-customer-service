"""OpenAI 相容視覺 OCR 引擎（Issue #78）。

走 ``{base_url}/chat/completions``，影像以 ``image_url`` data URL（base64）附上，
供 google（Gemini OpenAI 相容端點）/ openai / openrouter / litellm 共用。

- Prompt 沿用 Claude 引擎的結構化 prompt，額外附加抑制幻覺指令。
- 頁面分類：供應商 × 模型為 ``native_schema`` 等級時用 ``response_format``
  json_schema（Issue #70 能力表），否則純 prompt + 容錯解析。
- 用量取自 ``usage.prompt_tokens`` / ``usage.completion_tokens``。
- 錯誤：key 缺失 / 401 / 403 → ``OcrProcessingError("<供應商> auth error: ...")``，
  與 Claude 引擎的 ``AuthenticationError`` 訊息形狀一致，文件狀態 / 錯誤文字不分歧。
"""

from __future__ import annotations

import asyncio
import base64
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from src.domain.llm.structured_output import NATIVE_SCHEMA, capability
from src.domain.shared.exceptions import OcrProcessingError
from src.infrastructure.file_parser.ocr_engines._image import _compress_image
from src.infrastructure.file_parser.ocr_engines.base import (
    OcrClassifyResult,
    OcrEngine,
    OcrPageResult,
)
from src.infrastructure.file_parser.ocr_engines.prompts import (
    _CLASSIFY_PROMPT,
    _DEFAULT_PROMPT,
    _VALID_PAGE_TYPES,
    ANTI_HALLUCINATION_SUFFIX,
    normalize_page_type,
)
from src.infrastructure.llm.llm_caller import _BASE_URLS
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

ApiKeyResolver = Callable[[str], Awaitable[str]]

_PROVIDER_LABELS = {
    "google": "Gemini",
    "openai": "OpenAI",
    "openrouter": "OpenRouter",
    "litellm": "LiteLLM",
}

_CLASSIFY_JSON_HINT = (
    '\n以 JSON 物件輸出：{"page_type": "<catalog|promotion|mixed|cover>"}\n'
)

_PAGE_TYPE_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "page_type",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "page_type": {
                    "type": "string",
                    "enum": sorted(_VALID_PAGE_TYPES),
                }
            },
            "required": ["page_type"],
            "additionalProperties": False,
        },
    },
}


class _OcrAuthError(OcrProcessingError):
    """認證類錯誤（key 缺失 / 401 / 403）— 分類路徑不得吞掉、必須往上拋。"""


def _content_text(message: dict[str, Any]) -> str:
    """OpenAI 相容 content 可能是字串或 content-part 陣列（部分代理）。"""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


class OpenAICompatVisionOcrEngine(OcrEngine):
    """OCR engine over any OpenAI-compatible chat-completions vision endpoint."""

    def __init__(
        self,
        api_key_resolver: ApiKeyResolver | None,
        provider: str,
        model: str,
        base_url: str = "",
        max_concurrent: int = 5,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key_resolver = api_key_resolver
        self._provider = provider.strip().lower()
        self._model = model
        self._base_url = (base_url or _BASE_URLS.get(self._provider, "")).rstrip("/")
        if not self._base_url:
            raise ValueError(
                f"No OpenAI-compatible base_url known for provider '{provider}'"
            )
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._timeout = timeout
        self._transport = transport  # 測試注入 httpx.MockTransport 用

    # ── 屬性 ──

    @property
    def model_spec(self) -> str:
        return f"{self._provider}:{self._model}"

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def _label(self) -> str:
        return _PROVIDER_LABELS.get(self._provider, self._provider.title())

    # ── 內部 ──

    async def _resolve_api_key(self) -> str:
        api_key = ""
        if self._api_key_resolver is not None:
            api_key = await self._api_key_resolver(self._provider)
        if not api_key or not api_key.strip():
            raise _OcrAuthError(
                f"{self._label} auth error: API key not configured for provider "
                f"'{self._provider}' (empty or whitespace)"
            )
        return api_key.strip()

    async def _chat(
        self,
        image_bytes: bytes,
        prompt: str,
        max_tokens: int,
        response_format: dict[str, Any] | None = None,
    ) -> tuple[str, int, int]:
        """POST chat/completions；回傳 (text, prompt_tokens, completion_tokens)。"""
        api_key = await self._resolve_api_key()
        image_bytes, media_type = _compress_image(image_bytes)
        b64 = base64.standard_b64encode(image_bytes).decode()
        body: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        if response_format is not None:
            body["response_format"] = response_format

        url = f"{self._base_url}/chat/completions"
        try:
            async with self._semaphore:
                t0 = time.perf_counter()
                async with httpx.AsyncClient(
                    timeout=self._timeout, transport=self._transport
                ) as client:
                    resp = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {api_key}"},
                        json=body,
                    )
                elapsed_ms = round((time.perf_counter() - t0) * 1000)
        except httpx.HTTPError as e:
            raise OcrProcessingError(f"{self._label} API error: {e}") from e

        if resp.status_code in (401, 403):
            raise _OcrAuthError(
                f"{self._label} auth error: HTTP {resp.status_code} "
                f"{resp.text[:200]}"
            )
        if resp.status_code >= 400:
            raise OcrProcessingError(
                f"{self._label} API error: HTTP {resp.status_code} {resp.text[:200]}"
            )
        try:
            data = resp.json()
            text = _content_text(data["choices"][0]["message"])
            usage = data.get("usage") or {}
            in_tok = int(usage.get("prompt_tokens") or 0)
            out_tok = int(usage.get("completion_tokens") or 0)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise OcrProcessingError(
                f"{self._label} API error: malformed response ({e})"
            ) from e
        logger.info(
            "ocr.page.done",
            model=self.model_spec,
            media_type=media_type,
            image_kb=round(len(image_bytes) / 1024),
            input_tokens=in_tok,
            output_tokens=out_tok,
            elapsed_ms=elapsed_ms,
        )
        return text, in_tok, out_tok

    # ── OcrEngine ──

    async def ocr_page_with_usage(
        self, image_bytes: bytes, prompt: str | None = None
    ) -> OcrPageResult:
        full_prompt = (prompt or _DEFAULT_PROMPT) + ANTI_HALLUCINATION_SUFFIX
        text, in_tok, out_tok = await self._chat(
            image_bytes, full_prompt, max_tokens=8192
        )
        return OcrPageResult(
            text=text.strip(),
            input_tokens=in_tok,
            output_tokens=out_tok,
            model=self.model_spec,
        )

    async def classify_page_type_with_usage(
        self, image_bytes: bytes
    ) -> OcrClassifyResult:
        tier, _note = capability(self._provider, self._model)
        response_format = _PAGE_TYPE_RESPONSE_FORMAT if tier == NATIVE_SCHEMA else None
        prompt = _CLASSIFY_PROMPT + (_CLASSIFY_JSON_HINT if response_format else "")
        try:
            raw, in_tok, out_tok = await self._chat(
                image_bytes, prompt, max_tokens=40, response_format=response_format
            )
        except _OcrAuthError:
            raise
        except OcrProcessingError as e:
            # Classification 失敗不應卡住 OCR — fallback catalog（對齊 Claude 引擎）
            logger.warning(
                "ocr.classify.api_error",
                error=str(e)[:200],
                fallback="catalog",
            )
            return OcrClassifyResult(page_type="catalog", model=self.model_spec)
        page_type = normalize_page_type(raw, fallback="")
        if not page_type:
            logger.warning(
                "ocr.classify.invalid_response", raw=raw[:100], fallback="catalog"
            )
            page_type = "catalog"
        return OcrClassifyResult(
            page_type=page_type,
            input_tokens=in_tok,
            output_tokens=out_tok,
            model=self.model_spec,
        )
