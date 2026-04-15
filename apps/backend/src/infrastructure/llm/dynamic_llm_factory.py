import json
from collections.abc import AsyncIterator

from src.config import Settings
from src.domain.platform.model_registry import DEFAULT_MODELS as _REGISTRY
from src.domain.platform.services import EncryptionService
from src.domain.platform.value_objects import ProviderName, ProviderType
from src.domain.rag.services import LLMService
from src.domain.rag.value_objects import LLMResult
from src.domain.shared.cache_service import CacheService
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

# Default base URLs per provider
_DEFAULT_BASE_URLS: dict[str, str] = {
    ProviderName.OPENAI.value: "https://api.openai.com/v1",
    ProviderName.DEEPSEEK.value: "https://api.deepseek.com/v1",
    ProviderName.QWEN.value: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ProviderName.GOOGLE.value: "https://generativelanguage.googleapis.com/v1beta/openai",
    ProviderName.OPENROUTER.value: "https://openrouter.ai/api/v1",
    ProviderName.LITELLM.value: "https://litellm-server.pic-ai.work",
}

# Default model per provider
_DEFAULT_MODELS: dict[str, str] = {
    ProviderName.ANTHROPIC.value: "claude-sonnet-4-20250514",
    ProviderName.OPENAI.value: "gpt-4o",
    ProviderName.DEEPSEEK.value: "deepseek-chat",
    ProviderName.QWEN.value: "qwen-plus",
    ProviderName.GOOGLE.value: "gemini-2.5-flash-lite",
    ProviderName.OPENROUTER.value: "openai/gpt-4o",
    ProviderName.LITELLM.value: "azure_ai/claude-sonnet-4-5",
}

# Map provider_name -> Settings attribute for .env fallback API key
_ENV_KEY_MAP: dict[str, str] = {
    ProviderName.OPENAI.value: "effective_openai_api_key",
    ProviderName.DEEPSEEK.value: "deepseek_api_key",
    ProviderName.ANTHROPIC.value: "anthropic_api_key",
    ProviderName.GOOGLE.value: "google_api_key",
    ProviderName.QWEN.value: "qwen_api_key",
    ProviderName.OPENROUTER.value: "openrouter_api_key",
    ProviderName.LITELLM.value: "litellm_api_key",
}


def _build_llm_service_from_config(config: dict) -> LLMService:
    """Build LLM service from config dict (provider_name, api_key, model, base_url, pricing)."""
    provider_name = config["provider_name"]
    api_key = config["api_key"]
    model = config["model"]
    base_url = config.get("base_url", "")
    pricing = config.get("pricing", {})

    if provider_name == ProviderName.ANTHROPIC.value:
        from src.infrastructure.llm.anthropic_llm_service import (
            AnthropicLLMService,
        )
        return AnthropicLLMService(
            api_key=api_key, model=model, max_tokens=1024, pricing=pricing,
        )

    from src.infrastructure.llm.openai_llm_service import OpenAILLMService
    return OpenAILLMService(
        api_key=api_key,
        model=model,
        max_tokens=1024,
        pricing=pricing,
        base_url=base_url,
    )


class DynamicLLMServiceFactory:
    """Resolves LLM service: DB-first, .env fallback."""

    def __init__(
        self,
        provider_setting_repo_factory,  # Callable — creates a fresh repo each call
        encryption_service: EncryptionService,
        fallback_service: LLMService,
        cache_service: CacheService | None = None,
        cache_ttl: int = 300,
    ) -> None:
        self._repo_factory = provider_setting_repo_factory
        self._encryption = encryption_service
        self._fallback = fallback_service
        self._cache_service = cache_service
        self._cache_ttl = cache_ttl

    async def get_service(
        self,
        provider_name: str = "",
        model: str = "",
    ) -> LLMService:
        """Resolve LLM service.

        When *provider_name* / *model* are given, build a service matching
        those overrides (per-bot model selection).  Otherwise fall back to
        the system-wide default provider.
        """
        has_override = bool(provider_name or model)
        cache_key = (
            f"llm_config:{provider_name}:{model}"
            if has_override
            else "llm_config:default"
        )

        # Try cache first
        if self._cache_service is not None:
            cached = await self._cache_service.get(cache_key)
            if cached is not None:
                try:
                    config = json.loads(self._encryption.decrypt(cached))
                    return _build_llm_service_from_config(config)
                except Exception:
                    logger.warning("dynamic_llm.cache_decrypt_failed")

        try:
            repo = self._repo_factory()
            settings = await repo.find_all_by_type(ProviderType.LLM)
            enabled = [s for s in settings if s.is_enabled]
            if not enabled:
                logger.debug("dynamic_llm.fallback", reason="no_enabled_db_settings")
                return self._fallback

            # Select provider: override or first enabled
            if provider_name:
                setting = next(
                    (s for s in enabled if s.provider_name.value == provider_name),
                    None,
                )
                if setting is None:
                    logger.warning(
                        "dynamic_llm.override_not_found",
                        provider_name=provider_name,
                    )
                    setting = enabled[0]
            else:
                setting = enabled[0]

            # Resolve API key: DB-encrypted first, then .env fallback
            if setting.api_key_encrypted:
                api_key = self._encryption.decrypt(setting.api_key_encrypted)
            else:
                cfg = Settings()
                attr = _ENV_KEY_MAP.get(setting.provider_name.value, "")
                api_key = getattr(cfg, attr, "") if attr else ""

            # Resolve model: override → DB default → hardcoded default
            if model:
                resolved_model = model
            else:
                default_model = next(
                    (m.model_id for m in setting.models if m.is_default),
                    setting.models[0].model_id if setting.models else None,
                )
                resolved_model = default_model or _DEFAULT_MODELS.get(
                    setting.provider_name.value, ""
                )

            base_url = setting.base_url or _DEFAULT_BASE_URLS.get(
                setting.provider_name.value, ""
            )

            if setting.provider_name == ProviderName.MOCK:
                return self._fallback

            # Build pricing dict from DB models, fallback to registry
            pricing: dict[str, dict[str, float]] = {}
            registry_models = _REGISTRY.get(
                setting.provider_name.value, {},
            ).get("llm", [])
            registry_pricing = {
                rm["model_id"]: {
                    "input": rm["input_price"],
                    "output": rm["output_price"],
                }
                for rm in registry_models
                if rm.get("input_price", 0) > 0
                or rm.get("output_price", 0) > 0
            }
            for m in setting.models:
                if m.input_price > 0 or m.output_price > 0:
                    pricing[m.model_id] = {
                        "input": m.input_price,
                        "output": m.output_price,
                    }
                elif m.model_id in registry_pricing:
                    pricing[m.model_id] = registry_pricing[m.model_id]

            config = {
                "provider_name": setting.provider_name.value,
                "api_key": api_key,
                "model": resolved_model,
                "base_url": base_url,
                "pricing": pricing,
            }

            # Cache encrypted config
            if self._cache_service is not None:
                encrypted = self._encryption.encrypt(json.dumps(config))
                await self._cache_service.set(
                    cache_key, encrypted, ttl_seconds=self._cache_ttl
                )

            if has_override:
                logger.info(
                    "dynamic_llm.override_resolved",
                    provider=setting.provider_name.value,
                    model=resolved_model,
                )

            return _build_llm_service_from_config(config)
        except Exception:
            logger.exception("dynamic_llm.error")
            return self._fallback

    async def resolve_api_key(self, provider_name: str) -> str:
        """Resolve API key for a provider: DB-encrypted first, then .env fallback.

        Useful for code that calls provider SDKs directly (e.g. reranker).
        """
        try:
            repo = self._repo_factory()
            settings = await repo.find_all_by_type(ProviderType.LLM)
            enabled = [s for s in settings if s.is_enabled]
            setting = next(
                (s for s in enabled if s.provider_name.value == provider_name),
                None,
            )
            if setting and setting.api_key_encrypted:
                return self._encryption.decrypt(setting.api_key_encrypted)
        except Exception:
            logger.warning("resolve_api_key.db_failed", exc_info=True)

        # Fallback to .env
        cfg = Settings()
        attr = _ENV_KEY_MAP.get(provider_name, "")
        return getattr(cfg, attr, "") if attr else ""


class DynamicLLMServiceProxy(LLMService):
    """Proxy that delegates to DynamicLLMServiceFactory-resolved service."""

    @property
    def model_name(self) -> str:
        return "dynamic"

    def __init__(self, factory: DynamicLLMServiceFactory) -> None:
        self._factory = factory

    async def resolve_for_bot(
        self, provider_name: str = "", model: str = "",
    ) -> LLMService:
        """Build a bot-specific LLM service using factory overrides."""
        return await self._factory.get_service(
            provider_name=provider_name, model=model,
        )

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
    ) -> LLMResult:
        service = await self._factory.get_service()
        return await service.generate(
            system_prompt,
            user_message,
            context,
            temperature=temperature,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
        )

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
        usage_collector: dict | None = None,
    ) -> AsyncIterator[str]:
        service = await self._factory.get_service()
        async for token in service.generate_stream(
            system_prompt,
            user_message,
            context,
            temperature=temperature,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
            usage_collector=usage_collector,
        ):
            yield token
