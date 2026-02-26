import json
from collections.abc import AsyncIterator

from src.domain.platform.repository import ProviderSettingRepository
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
    ProviderName.QWEN.value: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ProviderName.GOOGLE.value: "https://generativelanguage.googleapis.com/v1beta/openai",
    ProviderName.OPENROUTER.value: "https://openrouter.ai/api/v1",
}

# Default model per provider
_DEFAULT_MODELS: dict[str, str] = {
    ProviderName.ANTHROPIC.value: "claude-sonnet-4-20250514",
    ProviderName.OPENAI.value: "gpt-4o",
    ProviderName.QWEN.value: "qwen-plus",
    ProviderName.GOOGLE.value: "gemini-2.5-flash-lite",
    ProviderName.OPENROUTER.value: "openai/gpt-4o",
}


def _build_llm_service_from_config(config: dict) -> LLMService:
    """Build LLM service from config dict (provider_name, api_key, model, base_url)."""
    provider_name = config["provider_name"]
    api_key = config["api_key"]
    model = config["model"]
    base_url = config.get("base_url", "")

    if provider_name == ProviderName.ANTHROPIC.value:
        from src.infrastructure.llm.anthropic_llm_service import (
            AnthropicLLMService,
        )
        return AnthropicLLMService(
            api_key=api_key, model=model, max_tokens=1024
        )

    from src.infrastructure.llm.openai_llm_service import OpenAILLMService
    return OpenAILLMService(
        api_key=api_key,
        model=model,
        max_tokens=1024,
        base_url=base_url,
    )


class DynamicLLMServiceFactory:
    """Resolves LLM service: DB-first, .env fallback."""

    def __init__(
        self,
        provider_setting_repository: ProviderSettingRepository,
        encryption_service: EncryptionService,
        fallback_service: LLMService,
        cache_service: CacheService | None = None,
        cache_ttl: int = 300,
    ) -> None:
        self._repository = provider_setting_repository
        self._encryption = encryption_service
        self._fallback = fallback_service
        self._cache_service = cache_service
        self._cache_ttl = cache_ttl

    async def get_service(self) -> LLMService:
        cache_key = "llm_config:default"

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
            settings = await self._repository.find_all_by_type(ProviderType.LLM)
            enabled = [s for s in settings if s.is_enabled]
            if not enabled:
                logger.debug("dynamic_llm.fallback", reason="no_enabled_db_settings")
                return self._fallback

            setting = enabled[0]
            api_key = self._encryption.decrypt(setting.api_key_encrypted)

            # Find default model
            default_model = next(
                (m.model_id for m in setting.models if m.is_default),
                setting.models[0].model_id if setting.models else None,
            )
            model = default_model or _DEFAULT_MODELS.get(
                setting.provider_name.value, ""
            )

            base_url = setting.base_url or _DEFAULT_BASE_URLS.get(
                setting.provider_name.value, ""
            )

            if setting.provider_name == ProviderName.FAKE:
                return self._fallback

            config = {
                "provider_name": setting.provider_name.value,
                "api_key": api_key,
                "model": model,
                "base_url": base_url,
            }

            # Cache encrypted config
            if self._cache_service is not None:
                encrypted = self._encryption.encrypt(json.dumps(config))
                await self._cache_service.set(
                    cache_key, encrypted, ttl_seconds=self._cache_ttl
                )

            return _build_llm_service_from_config(config)
        except Exception:
            logger.exception("dynamic_llm.error")
            return self._fallback


class DynamicLLMServiceProxy(LLMService):
    """Proxy that delegates to DynamicLLMServiceFactory-resolved service."""

    def __init__(self, factory: DynamicLLMServiceFactory) -> None:
        self._factory = factory

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
    ) -> AsyncIterator[str]:
        service = await self._factory.get_service()
        async for token in service.generate_stream(
            system_prompt,
            user_message,
            context,
            temperature=temperature,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
        ):
            yield token
