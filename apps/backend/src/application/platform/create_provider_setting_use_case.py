from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.domain.platform.entity import ProviderSetting
from src.domain.platform.model_registry import DEFAULT_MODELS
from src.domain.platform.repository import ProviderSettingRepository
from src.domain.platform.services import EncryptionService
from src.domain.platform.value_objects import (
    ModelConfig,
    ProviderName,
    ProviderSettingId,
    ProviderType,
)
from src.domain.shared.cache_service import CacheService
from src.domain.shared.exceptions import DuplicateEntityError


@dataclass(frozen=True)
class CreateProviderSettingCommand:
    provider_type: str
    provider_name: str
    display_name: str
    api_key: str
    base_url: str = ""
    models: list[dict[str, Any]] = field(default_factory=list)
    extra_config: dict[str, Any] = field(default_factory=dict)


_PROVIDER_TYPE_CACHE_KEYS = {
    ProviderType.LLM: "llm_config:default",
    ProviderType.EMBEDDING: "embedding_config:default",
}


class CreateProviderSettingUseCase:
    def __init__(
        self,
        provider_setting_repository: ProviderSettingRepository,
        encryption_service: EncryptionService,
        cache_service: CacheService | None = None,
    ) -> None:
        self._repository = provider_setting_repository
        self._encryption = encryption_service
        self._cache_service = cache_service

    async def execute(
        self, command: CreateProviderSettingCommand
    ) -> ProviderSetting:
        provider_type = ProviderType(command.provider_type)
        provider_name = ProviderName(command.provider_name)

        existing = await self._repository.find_by_type_and_name(
            provider_type, provider_name
        )
        if existing is not None:
            raise DuplicateEntityError(
                "ProviderSetting",
                "provider_type+provider_name",
                f"{command.provider_type}+{command.provider_name}",
            )

        raw_models = command.models
        if not raw_models:
            registry = DEFAULT_MODELS.get(command.provider_name, {})
            raw_models = registry.get(command.provider_type, [])

        models = [
            ModelConfig(
                model_id=m["model_id"],
                display_name=m["display_name"],
                is_default=m.get("is_default", False),
                is_enabled=m.get("is_enabled", True),
                price=m.get("price", ""),
                description=m.get("description", ""),
            )
            for m in raw_models
        ]

        encrypted_key = (
            self._encryption.encrypt(command.api_key)
            if command.api_key
            else ""
        )

        # Embedding provider 互斥：建立新的時停用其他已啟用的
        if provider_type == ProviderType.EMBEDDING:
            all_embedding = await self._repository.find_all_by_type(
                ProviderType.EMBEDDING
            )
            for other in all_embedding:
                if other.is_enabled:
                    other.is_enabled = False
                    other.updated_at = datetime.now(timezone.utc)
                    await self._repository.save(other)

        setting = ProviderSetting(
            id=ProviderSettingId(),
            provider_type=provider_type,
            provider_name=provider_name,
            display_name=command.display_name,
            is_enabled=True,
            api_key_encrypted=encrypted_key,
            base_url=command.base_url,
            models=models,
            extra_config=command.extra_config,
        )

        await self._repository.save(setting)
        if self._cache_service is not None:
            cache_key = _PROVIDER_TYPE_CACHE_KEYS.get(provider_type)
            if cache_key:
                await self._cache_service.delete(cache_key)
        return setting
