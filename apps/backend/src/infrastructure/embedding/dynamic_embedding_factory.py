"""Embedding is fixed to OpenAI text-embedding-3-small (1536 dim).

API key resolution: DB (OpenAI LLM provider) → .env fallback.
"""

import json

from src.config import Settings
from src.domain.platform.services import EncryptionService
from src.domain.platform.value_objects import ProviderName, ProviderType
from src.domain.rag.services import EmbeddingService
from src.domain.shared.cache_service import CacheService
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

_FIXED_MODEL = "text-embedding-3-small"
_FIXED_BASE_URL = "https://api.openai.com/v1"


def _build_embedding_service(api_key: str) -> EmbeddingService:
    """Build OpenAI embedding service with fixed model."""
    from src.infrastructure.embedding.openai_embedding_service import (
        OpenAIEmbeddingService,
    )
    return OpenAIEmbeddingService(
        api_key=api_key,
        model=_FIXED_MODEL,
        base_url=_FIXED_BASE_URL,
    )


class DynamicEmbeddingServiceFactory:
    """Resolves Embedding service: OpenAI API key from DB or .env."""

    def __init__(
        self,
        provider_setting_repo_factory,  # Callable — creates a fresh repo each call
        encryption_service: EncryptionService,
        fallback_service: EmbeddingService,
        cache_service: CacheService | None = None,
        cache_ttl: int = 300,
    ) -> None:
        self._repo_factory = provider_setting_repo_factory
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
                    return _build_embedding_service(config["api_key"])
                except Exception:
                    logger.warning("dynamic_embedding.cache_decrypt_failed")

        try:
            api_key = await self._resolve_api_key()
            if not api_key:
                logger.debug(
                    "dynamic_embedding.fallback",
                    reason="no_api_key",
                )
                return self._fallback

            config = {"api_key": api_key}

            # Cache encrypted config
            if self._cache_service is not None:
                encrypted = self._encryption.encrypt(json.dumps(config))
                await self._cache_service.set(
                    cache_key, encrypted, ttl_seconds=self._cache_ttl
                )

            return _build_embedding_service(api_key)
        except Exception:
            logger.exception("dynamic_embedding.error")
            return self._fallback

    async def _resolve_api_key(self) -> str:
        """Resolve OpenAI API key: DB (OpenAI LLM provider) → .env."""
        repo = self._repo_factory()

        # Try OpenAI LLM provider's key from DB
        setting = await repo.find_by_type_and_name(
            ProviderType.LLM, ProviderName.OPENAI
        )
        if setting and setting.api_key_encrypted:
            return self._encryption.decrypt(setting.api_key_encrypted)

        # Try OpenAI Embedding provider's key from DB (legacy records)
        setting = await repo.find_by_type_and_name(
            ProviderType.EMBEDDING, ProviderName.OPENAI
        )
        if setting and setting.api_key_encrypted:
            return self._encryption.decrypt(setting.api_key_encrypted)

        # .env fallback
        cfg = Settings()
        return cfg.effective_embedding_api_key or cfg.effective_openai_api_key


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
