from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.repository import KnowledgeBaseRepository


class ListKnowledgeBasesUseCase:
    def __init__(
        self, knowledge_base_repository: KnowledgeBaseRepository
    ) -> None:
        self._knowledge_base_repository = knowledge_base_repository

    async def execute(
        self,
        tenant_id: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[KnowledgeBase]:
        return await self._knowledge_base_repository.find_all_by_tenant(
            tenant_id, limit=limit, offset=offset,
        )

    async def count(self, tenant_id: str) -> int:
        return await self._knowledge_base_repository.count_by_tenant(tenant_id)
