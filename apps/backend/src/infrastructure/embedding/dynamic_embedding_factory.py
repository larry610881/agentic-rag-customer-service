from src.domain.platform.repository import ProviderSettingRepository
from src.domain.platform.services import EncryptionService
from src.domain.platform.value_objects import ProviderName, ProviderType
from src.domain.rag.services import EmbeddingService
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


class DynamicEmbeddingServiceFactory:
    """Resolves Embedding service: DB-first, .env fallback."""

    def __init__(
        self,
        provider_setting_repository: ProviderSettingRepository,
        encryption_service: EncryptionService,
        fallback_service: EmbeddingService,
    ) -> None:
        self._repository = provider_setting_repository
        self._encryption = encryption_service
        self._fallback = fallback_service

    async def get_service(self) -> EmbeddingService:
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

            from src.infrastructure.embedding.openai_embedding_service import (
                OpenAIEmbeddingService,
            )
            return OpenAIEmbeddingService(
                api_key=api_key,
                model=model,
                base_url=base_url,
            )
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
