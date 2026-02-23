from abc import ABC, abstractmethod

from src.domain.tenant.entity import Tenant


class TenantRepository(ABC):
    @abstractmethod
    async def save(self, tenant: Tenant) -> None: ...

    @abstractmethod
    async def find_by_id(self, tenant_id: str) -> Tenant | None: ...

    @abstractmethod
    async def find_by_name(self, name: str) -> Tenant | None: ...

    @abstractmethod
    async def find_all(self) -> list[Tenant]: ...
