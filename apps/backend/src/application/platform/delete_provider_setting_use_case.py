from src.domain.platform.repository import ProviderSettingRepository
from src.domain.shared.exceptions import EntityNotFoundError


class DeleteProviderSettingUseCase:
    def __init__(
        self,
        provider_setting_repository: ProviderSettingRepository,
    ) -> None:
        self._repository = provider_setting_repository

    async def execute(self, setting_id: str) -> None:
        setting = await self._repository.find_by_id(setting_id)
        if setting is None:
            raise EntityNotFoundError("ProviderSetting", setting_id)
        await self._repository.delete(setting_id)
