from abc import ABC, abstractmethod

from src.domain.auth.entity import User


class UserRepository(ABC):
    @abstractmethod
    async def save(self, user: User) -> None: ...

    @abstractmethod
    async def find_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def find_all(
        self,
        *,
        tenant_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[User]: ...

    @abstractmethod
    async def find_all_by_tenant(
        self,
        tenant_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[User]: ...

    @abstractmethod
    async def count_all(
        self, *, tenant_id: str | None = None
    ) -> int: ...

    @abstractmethod
    async def delete(self, user_id: str) -> None: ...

    @abstractmethod
    async def find_admin_email_by_tenant(
        self, tenant_id: str
    ) -> str | None:
        """回該租戶任一 admin 角色的 email；無則 None。S-Token-Gov.3.5"""
        ...
