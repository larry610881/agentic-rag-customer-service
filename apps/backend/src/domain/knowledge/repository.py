from abc import ABC, abstractmethod

from src.domain.knowledge.entity import KnowledgeBase


class KnowledgeBaseRepository(ABC):
    @abstractmethod
    async def save(self, knowledge_base: KnowledgeBase) -> None: ...

    @abstractmethod
    async def find_by_id(self, kb_id: str) -> KnowledgeBase | None: ...

    @abstractmethod
    async def find_all_by_tenant(
        self, tenant_id: str
    ) -> list[KnowledgeBase]: ...
