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
    async def find_all_by_tenant(self, tenant_id: str) -> list[User]: ...
