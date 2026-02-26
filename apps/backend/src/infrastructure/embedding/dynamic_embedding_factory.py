import json

from src.domain.platform.repository import ProviderSettingRepository
from src.domain.platform.services import EncryptionService
from src.domain.platform.value_objects import ProviderName, ProviderType
from src.domain.rag.services import EmbeddingService
from src.domain.shared.cache_service import CacheService
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_BASE_URLS: dict[str, str] = {
    ProviderName.OPENAI.value: "https://api.openai.com/v1",
    ProviderName.QWEN.value: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ProviderName.GOOGLE.value: "https://generativelanguage.googleapis.com/v1beta/openai",
}

_DEFAULT_MODELS: dict[str, str] = {
    ProviderName.OPENAI.value: "text-embedding-3-small",
    ProviderName.QWEN.value: "text-embedding-v3",
    ProviderName.GOOGLE.value: "text-embedding-004",
}


def _build_embedding_service_from_config(config: dict) -> EmbeddingService:
    """Build Embedding service from config dict."""
    from src.infrastructure.embedding.openai_embedding_service import (
        OpenAIEmbeddingService,
    )
    return OpenAIEmbeddingService(
        api_key=config["api_key"],
        model=config["model"],
        base_url=config.get("base_url", "https://api.openai.com/v1"),
    )


class DynamicEmbeddingServiceFactory:
    """Resolves Embedding service: DB-first, .env fallback."""

    def __init__(
        self,
        provider_setting_repository: ProviderSettingRepository,
        encryption_service: EncryptionService,
        fallback_service: EmbeddingService,
        cache_service: CacheService | None = None,
        cache_ttl: int = 300,
    ) -> None:
        self._repository = provider_setting_repository
        self._encryption = encryption_service
        self._fallback = fallback_service
        self._cache_service = cache_service
        self._cache_ttl = cache_ttl

    async def get_service(self) -> EmbeddingService:
        cache_key = "embedding_config:default"

        # Try cache first
        if self._cache_service is not None:
            cached = await self._cache_service.get(cache_key)
            if cached is not None:
                try:
                    config = json.loads(self._encryption.decrypt(cached))
                    return _build_embedding_service_from_config(config)
                except Exception:
                    logger.warning("dynamic_embedding.cache_decrypt_failed")

        try:
            settings = await self._repository.find_all_by_type(
                ProviderType.EMBEDDING
            )
            enabled = [s for s in settings if s.is_enabled]
            if not enabled:
                logger.debug(
                    "dynamic_embedding.fallback",
                    reason="no_enabled_db_settings",
                )
                return self._fallback

            setting = enabled[0]
            api_key = self._encryption.decrypt(setting.api_key_encrypted)

            default_model = next(
                (m.model_id for m in setting.models if m.is_default),
                setting.models[0].model_id if setting.models else None,
            )
            model = default_model or _DEFAULT_MODELS.get(
                setting.provider_name.value, "text-embedding-3-small"
            )

            base_url = setting.base_url or _DEFAULT_BASE_URLS.get(
                setting.provider_name.value, "https://api.openai.com/v1"
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

            return _build_embedding_service_from_config(config)
        except Exception:
            logger.exception("dynamic_embedding.error")
            return self._fallback


class DynamicEmbeddingServiceProxy(EmbeddingService):
    """Proxy that delegates to DynamicEmbeddingServiceFactory-resolved service."""

    def __init__(self, factory: DynamicEmbeddingServiceFactory) -> None:
        self._factory = factory

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        service = await self._factory.get_service()
        return await service.embed_texts(texts)

    async def embed_query(self, text: str) -> list[float]:
        service = await self._factory.get_service()
        return await service.embed_query(text)
