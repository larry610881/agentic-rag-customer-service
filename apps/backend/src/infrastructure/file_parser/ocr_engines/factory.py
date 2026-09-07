"""依 model spec 動態選 OCR 引擎（Issue #78）。

spec 格式 ``provider:model``：
- ``anthropic:*`` → :class:`ClaudeVisionOcrEngine`
- ``google|openai|openrouter|litellm:*`` → :class:`OpenAICompatVisionOcrEngine`
  （base_url 沿用 ``llm_caller._BASE_URLS``，google 走 Gemini OpenAI 相容端點）

引擎依 spec 快取（同 spec 共用實例；引擎本身無跨呼叫的可變狀態，用量由
每次呼叫的結果帶回）。API key 一律透過 ``api_key_resolver`` 延遲解析
（``DynamicLLMFactory.resolve_api_key``：DB 加密設定優先，退回 .env）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.domain.knowledge.ocr_model_spec import (
    ANTHROPIC_PROVIDER,
    normalize_ocr_model_spec,
    parse_ocr_model_spec,
    validate_ocr_model_spec,
)
from src.infrastructure.file_parser.ocr_engines.base import OcrEngine
from src.infrastructure.file_parser.ocr_engines.claude_vision_ocr import (
    ClaudeVisionOcrEngine,
)
from src.infrastructure.file_parser.ocr_engines.openai_compat_vision_ocr import (
    OpenAICompatVisionOcrEngine,
)
from src.infrastructure.llm.llm_caller import _BASE_URLS

ApiKeyResolver = Callable[[str], Awaitable[str]]

DEFAULT_OCR_MODEL_SPEC = "anthropic:claude-sonnet-4-6"


class DynamicOcrEngineFactory:
    def __init__(
        self,
        api_key_resolver: ApiKeyResolver | None = None,
        default_spec: str = DEFAULT_OCR_MODEL_SPEC,
        max_concurrent: int = 5,
    ) -> None:
        self._api_key_resolver = api_key_resolver
        self._default_spec = (
            validate_ocr_model_spec(default_spec) or DEFAULT_OCR_MODEL_SPEC
        )
        self._max_concurrent = max_concurrent
        self._engines: dict[str, OcrEngine] = {}

    @property
    def default_spec(self) -> str:
        return self._default_spec

    def resolve_spec(
        self, kb_ocr_model: str, tenant_default_ocr_model: str, env_default: str = ""
    ) -> str:
        """優先序：KB.ocr_model → 租戶 default_ocr_model → 環境預設。"""
        for candidate in (kb_ocr_model, tenant_default_ocr_model, env_default):
            normalized = normalize_ocr_model_spec(candidate or "")
            if normalized:
                return normalized
        return self._default_spec

    def engine_for(self, spec: str) -> OcrEngine:
        """回傳 spec 對應的引擎；供應商不支援 → ``ValidationError``。"""
        normalized = validate_ocr_model_spec(spec) or self._default_spec
        engine = self._engines.get(normalized)
        if engine is None:
            engine = self._build(normalized)
            self._engines[normalized] = engine
        return engine

    def _build(self, spec: str) -> OcrEngine:
        provider, model = parse_ocr_model_spec(spec)
        if provider == ANTHROPIC_PROVIDER:
            return ClaudeVisionOcrEngine(
                model=model,
                max_concurrent=self._max_concurrent,
                api_key_resolver=self._api_key_resolver,
            )
        return OpenAICompatVisionOcrEngine(
            api_key_resolver=self._api_key_resolver,
            provider=provider,
            model=model,
            base_url=_BASE_URLS.get(provider, ""),
            max_concurrent=self._max_concurrent,
        )
