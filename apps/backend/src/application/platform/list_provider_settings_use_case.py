from src.domain.platform.entity import ProviderSetting
from src.domain.platform.repository import ProviderSettingRepository
from src.domain.platform.value_objects import ProviderType


class ListProviderSettingsUseCase:
    def __init__(
        self,
        provider_setting_repository: ProviderSettingRepository,
    ) -> None:
        self._repository = provider_setting_repository

    async def execute(
        self, provider_type: str | None = None
    ) -> list[ProviderSetting]:
        if provider_type:
            return await self._repository.find_all_by_type(
                ProviderType(provider_type)
            )
        return await self._repository.find_all()
