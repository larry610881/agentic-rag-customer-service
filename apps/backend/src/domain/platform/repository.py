from abc import ABC, abstractmethod

from src.domain.platform.entity import ProviderSetting
from src.domain.platform.value_objects import ProviderName, ProviderType


class ProviderSettingRepository(ABC):
    @abstractmethod
    async def save(self, setting: ProviderSetting) -> None: ...

    @abstractmethod
    async def find_by_id(self, setting_id: str) -> ProviderSetting | None: ...

    @abstractmethod
    async def find_by_type_and_name(
        self, provider_type: ProviderType, provider_name: ProviderName
    ) -> ProviderSetting | None: ...

    @abstractmethod
    async def find_all_by_type(
        self, provider_type: ProviderType
    ) -> list[ProviderSetting]: ...

    @abstractmethod
    async def find_all(self) -> list[ProviderSetting]: ...

    @abstractmethod
    async def delete(self, setting_id: str) -> None: ...
