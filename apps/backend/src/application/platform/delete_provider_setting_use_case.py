from src.domain.platform.repository import ProviderSettingRepository
from src.domain.platform.value_objects import ProviderType
from src.domain.shared.cache_service import CacheService
from src.domain.shared.exceptions import EntityNotFoundError

_PROVIDER_TYPE_CACHE_KEYS = {
    ProviderType.LLM: "llm_config:default",
    ProviderType.EMBEDDING: "embedding_config:default",
}


class DeleteProviderSettingUseCase:
    def __init__(
        self,
        provider_setting_repository: ProviderSettingRepository,
        cache_service: CacheService | None = None,
    ) -> None:
        self._repository = provider_setting_repository
        self._cache_service = cache_service

    async def execute(self, setting_id: str) -> None:
        setting = await self._repository.find_by_id(setting_id)
        if setting is None:
            raise EntityNotFoundError("ProviderSetting", setting_id)
        await self._repository.delete(setting_id)
        if self._cache_service is not None:
            cache_key = _PROVIDER_TYPE_CACHE_KEYS.get(setting.provider_type)
            if cache_key:
                await self._cache_service.delete(cache_key)
