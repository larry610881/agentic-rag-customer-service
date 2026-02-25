from dataclasses import dataclass, field
from typing import Any

from src.domain.platform.entity import ProviderSetting
from src.domain.platform.repository import ProviderSettingRepository
from src.domain.platform.services import EncryptionService
from src.domain.platform.value_objects import (
    ModelConfig,
    ProviderName,
    ProviderSettingId,
    ProviderType,
)
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


class CreateProviderSettingUseCase:
    def __init__(
        self,
        provider_setting_repository: ProviderSettingRepository,
        encryption_service: EncryptionService,
    ) -> None:
        self._repository = provider_setting_repository
        self._encryption = encryption_service

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

        models = [
            ModelConfig(
                model_id=m["model_id"],
                display_name=m["display_name"],
                is_default=m.get("is_default", False),
            )
            for m in command.models
        ]

        encrypted_key = (
            self._encryption.encrypt(command.api_key)
            if command.api_key
            else ""
        )

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
        return setting
