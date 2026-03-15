from abc import ABC, abstractmethod

from src.domain.memory.entity import MemoryFact, VisitorIdentity, VisitorProfile


class VisitorProfileRepository(ABC):
    @abstractmethod
    async def save(self, profile: VisitorProfile) -> None: ...

    @abstractmethod
    async def find_by_id(self, profile_id: str) -> VisitorProfile | None: ...

    @abstractmethod
    async def find_identity(
        self, tenant_id: str, source: str, external_id: str
    ) -> VisitorIdentity | None: ...

    @abstractmethod
    async def save_identity(self, identity: VisitorIdentity) -> None: ...


class MemoryFactRepository(ABC):
    @abstractmethod
    async def save(self, fact: MemoryFact) -> None: ...

    @abstractmethod
    async def upsert_by_key(self, fact: MemoryFact) -> None:
        """Insert or update by (profile_id, key) unique constraint."""
        ...

    @abstractmethod
    async def find_by_profile(
        self,
        profile_id: str,
        *,
        memory_type: str | None = None,
        include_expired: bool = False,
    ) -> list[MemoryFact]: ...

    @abstractmethod
    async def delete(self, fact_id: str) -> None: ...
