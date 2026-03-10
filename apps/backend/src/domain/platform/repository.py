from abc import ABC, abstractmethod

from src.domain.platform.entity import (
    McpServerRegistration,
    ProviderSetting,
    SystemPromptConfig,
)
from src.domain.platform.value_objects import ProviderName, ProviderType


class SystemPromptConfigRepository(ABC):
    @abstractmethod
    async def get(self) -> SystemPromptConfig: ...

    @abstractmethod
    async def save(self, config: SystemPromptConfig) -> None: ...


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


class McpServerRegistrationRepository(ABC):
    @abstractmethod
    async def save(self, server: McpServerRegistration) -> None: ...

    @abstractmethod
    async def find_by_id(self, id: str) -> McpServerRegistration | None: ...

    @abstractmethod
    async def find_all(self) -> list[McpServerRegistration]: ...

    @abstractmethod
    async def find_by_url(self, url: str) -> McpServerRegistration | None: ...

    @abstractmethod
    async def delete(self, id: str) -> None: ...
