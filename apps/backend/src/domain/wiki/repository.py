"""Wiki BC repository interface.

所有查詢**必須**帶 tenant_id 做租戶隔離。
"""

from abc import ABC, abstractmethod

from src.domain.wiki.entity import WikiGraph


class WikiGraphRepository(ABC):
    @abstractmethod
    async def save(self, wiki_graph: WikiGraph) -> None: ...

    @abstractmethod
    async def find_by_id(self, wiki_graph_id: str) -> WikiGraph | None: ...

    @abstractmethod
    async def find_by_bot_id(
        self, tenant_id: str, bot_id: str
    ) -> WikiGraph | None:
        """Find the (at most one) wiki graph bound to a bot."""
        ...

    @abstractmethod
    async def find_all_by_tenant(
        self,
        tenant_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[WikiGraph]: ...

    @abstractmethod
    async def count_by_tenant(self, tenant_id: str) -> int: ...

    @abstractmethod
    async def delete(self, wiki_graph_id: str) -> None: ...

    @abstractmethod
    async def delete_by_bot_id(
        self, tenant_id: str, bot_id: str
    ) -> None: ...
