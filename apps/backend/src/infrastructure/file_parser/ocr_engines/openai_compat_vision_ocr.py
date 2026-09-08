"""OpenAI 相容視覺 OCR 引擎（Issue #78）。

走 ``{base_url}/chat/completions``，影像以 ``image_url`` data URL（base64）附上，
供 google（Gemini OpenAI 相容端點）/ openai / openrouter / litellm 共用。

- Prompt 沿用 Claude 引擎的結構化 prompt，額外附加抑制幻覺指令。
- 頁面分類（Issue #81 三段式退避；Gemini 搭配 json_schema + 影像時 content 常為空）：
  1. 供應商 × 模型為 ``native_schema`` 等級 → ``response_format`` json_schema
  2. 內容空 / 無法解析 → 不帶 response_format、prompt 明示「只輸出 JSON」重試一次
  3. 仍無法解析 → 對原始文字做容錯正則擷取四個標籤之一
  4. 最後才退回 catalog。分類呼叫一律 ``max_tokens`` 64 並對 Gemini / gpt-5 送
  ``reasoning_effort: none``（thinking 會吃掉小額輸出預算）。
- 用量取自 ``usage.prompt_tokens`` / ``usage.completion_tokens``。
- 錯誤：key 缺失 / 401 / 403 → ``OcrProcessingError("<供應商> auth error: ...")``，
  與 Claude 引擎的 ``AuthenticationError`` 訊息形狀一致，文件狀態 / 錯誤文字不分歧。
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
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
# 步驟 2（純 prompt 重試）用：對 Gemini 需明示只輸出 JSON、不要任何說明文字
_CLASSIFY_PROMPT_ONLY_HINT = (
    '\n只輸出 JSON：{"page_type": "catalog|promotion|mixed|cover"}，'
    "不要輸出任何其他文字或說明。\n"
)
# 分類輸出只有一個小 JSON，但 thinking 模型會先吃掉輸出預算，不能只給 40
_CLASSIFY_MAX_TOKENS = 64
# 步驟 3：容錯擷取（不用 \b — CJK 在 Unicode 下屬 \w，「頁型是promotion」會漏抓）
_PAGE_TYPE_TOKEN_RE = re.compile(
    "(?<![a-z])(" + "|".join(sorted(_VALID_PAGE_TYPES)) + ")(?![a-z])",
    re.IGNORECASE,
)


def _no_thinking_effort(model: str) -> str | None:
    """分類呼叫關掉 thinking 的 reasoning_effort 值；不支援的模型回 None（不夾帶）。

    Gemini OpenAI 相容端點與 gpt-5 系列接受 ``"none"``；其他模型（gpt-4o /
    o-series / 聚合器上的開源模型）收到未知參數可能 400，一律不送。
    """
    return "none" if model.lower().startswith(("gemini", "gpt-5")) else None


@dataclass(frozen=True)
class _ChatReply:
    text: str
    input_tokens: int
    output_tokens: int
    finish_reason: str | None = None
    has_parsed: bool = False
    refusal: str | None = None

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
    """OpenAI 相容 content 可能是字串或 content-part 陣列（部分代理）。

    content 為空但 ``parsed`` 為物件（結構化輸出代理把結果放這裡）時，
    以其 JSON 字串代替，讓分類路徑不必為此重試。
    """
    content = message.get("content")
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    if not text.strip() and isinstance(message.get("parsed"), dict):
        text = json.dumps(message["parsed"], ensure_ascii=False)
    return text


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
        reasoning_effort: str | None = None,
    ) -> _ChatReply:
        """POST chat/completions；回傳文字、用量與診斷欄位（finish_reason 等）。"""
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
        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort

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
            choice = data["choices"][0]
            message = choice["message"]
            text = _content_text(message)
            usage = data.get("usage") or {}
            in_tok = int(usage.get("prompt_tokens") or 0)
            out_tok = int(usage.get("completion_tokens") or 0)
            finish_reason = choice.get("finish_reason")
            has_parsed = isinstance(message.get("parsed"), dict)
            refusal = message.get("refusal")
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
        return _ChatReply(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            finish_reason=finish_reason if isinstance(finish_reason, str) else None,
            has_parsed=has_parsed,
            refusal=refusal if isinstance(refusal, str) else None,
        )

    # ── OcrEngine ──

    async def ocr_page_with_usage(
        self, image_bytes: bytes, prompt: str | None = None
    ) -> OcrPageResult:
        full_prompt = (prompt or _DEFAULT_PROMPT) + ANTI_HALLUCINATION_SUFFIX
        reply = await self._chat(image_bytes, full_prompt, max_tokens=8192)
        return OcrPageResult(
            text=reply.text.strip(),
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            model=self.model_spec,
        )

    async def classify_page_type_with_usage(
        self, image_bytes: bytes
    ) -> OcrClassifyResult:
        """頁型分類（Issue #81 三段式退避，見模組 docstring）。

        用量為所有嘗試的加總（每次呼叫都真的計費）。認證錯誤往上拋；其他 API
        錯誤與解析失敗一律退回 catalog，不能卡住 OCR（對齊 Claude 引擎）。
        """
        tier, _note = capability(self._provider, self._model)
        effort = _no_thinking_effort(self._model)
        in_tok = out_tok = 0
        raws: list[str] = []
        try:
            if tier == NATIVE_SCHEMA:
                reply = await self._chat(
                    image_bytes,
                    _CLASSIFY_PROMPT + _CLASSIFY_JSON_HINT,
                    max_tokens=_CLASSIFY_MAX_TOKENS,
                    response_format=_PAGE_TYPE_RESPONSE_FORMAT,
                    reasoning_effort=effort,
                )
                in_tok += reply.input_tokens
                out_tok += reply.output_tokens
                page_type = normalize_page_type(reply.text, fallback="")
                if page_type:
                    return self._classified(page_type, 1, in_tok, out_tok)
                raws.append(reply.text)
                logger.warning(
                    "ocr.classify.native_schema_empty",
                    model=self.model_spec,
                    finish_reason=reply.finish_reason,
                    has_parsed=reply.has_parsed,
                    refusal=(reply.refusal or "")[:100] or None,
                    input_tokens=reply.input_tokens,
                    output_tokens=reply.output_tokens,
                    raw=reply.text[:100],
                    retry="prompt_only",
                )
                prompt = _CLASSIFY_PROMPT + _CLASSIFY_PROMPT_ONLY_HINT
            else:
                prompt = _CLASSIFY_PROMPT
            reply = await self._chat(
                image_bytes,
                prompt,
                max_tokens=_CLASSIFY_MAX_TOKENS,
                reasoning_effort=effort,
            )
            in_tok += reply.input_tokens
            out_tok += reply.output_tokens
            raws.append(reply.text)
            page_type = normalize_page_type(reply.text, fallback="")
            if page_type:
                return self._classified(page_type, 2, in_tok, out_tok)
        except _OcrAuthError:
            raise
        except OcrProcessingError as e:
            # Classification 失敗不應卡住 OCR — fallback catalog（對齊 Claude 引擎）
            logger.warning(
                "ocr.classify.api_error",
                error=str(e)[:200],
                step="fallback",
                fallback="catalog",
            )
            return OcrClassifyResult(
                page_type="catalog",
                input_tokens=in_tok,
                output_tokens=out_tok,
                model=self.model_spec,
            )
        for raw in raws:
            match = _PAGE_TYPE_TOKEN_RE.search(raw)
            if match:
                return self._classified(match.group(1).lower(), 3, in_tok, out_tok)
        logger.warning(
            "ocr.classify.invalid_response",
            model=self.model_spec,
            step="fallback",
            attempts=len(raws),
            raw=(raws[-1] if raws else "")[:100],
            fallback="catalog",
        )
        return OcrClassifyResult(
            page_type="catalog",
            input_tokens=in_tok,
            output_tokens=out_tok,
            model=self.model_spec,
        )

    def _classified(
        self, page_type: str, step: int, in_tok: int, out_tok: int
    ) -> OcrClassifyResult:
        logger.info(
            "ocr.classify.done",
            model=self.model_spec,
            page_type=page_type,
            step=step,
            input_tokens=in_tok,
            output_tokens=out_tok,
        )
        return OcrClassifyResult(
            page_type=page_type,
            input_tokens=in_tok,
            output_tokens=out_tok,
            model=self.model_spec,
        )
