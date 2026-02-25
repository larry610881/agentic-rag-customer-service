from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.domain.platform.entity import ProviderSetting
from src.domain.platform.repository import ProviderSettingRepository
from src.domain.platform.services import EncryptionService
from src.domain.platform.value_objects import ModelConfig
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class UpdateProviderSettingCommand:
    setting_id: str
    display_name: str | None = None
    is_enabled: bool | None = None
    api_key: str | None = None
    base_url: str | None = None
    models: list[dict[str, Any]] | None = None
    extra_config: dict[str, Any] | None = None


class UpdateProviderSettingUseCase:
    def __init__(
        self,
        provider_setting_repository: ProviderSettingRepository,
        encryption_service: EncryptionService,
    ) -> None:
        self._repository = provider_setting_repository
        self._encryption = encryption_service

    async def execute(
        self, command: UpdateProviderSettingCommand
    ) -> ProviderSetting:
        setting = await self._repository.find_by_id(command.setting_id)
        if setting is None:
            raise EntityNotFoundError("ProviderSetting", command.setting_id)

        if command.display_name is not None:
            setting.display_name = command.display_name
        if command.is_enabled is not None:
            setting.is_enabled = command.is_enabled
        if command.api_key is not None:
            setting.api_key_encrypted = self._encryption.encrypt(command.api_key)
        if command.base_url is not None:
            setting.base_url = command.base_url
        if command.models is not None:
            setting.models = [
                ModelConfig(
                    model_id=m["model_id"],
                    display_name=m["display_name"],
                    is_default=m.get("is_default", False),
                )
                for m in command.models
            ]
        if command.extra_config is not None:
            setting.extra_config = command.extra_config

        setting.updated_at = datetime.now(timezone.utc)
        await self._repository.save(setting)
        return setting
