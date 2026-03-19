from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.repository import KnowledgeBaseRepository


class ListAllKnowledgeBasesUseCase:
    def __init__(
        self, knowledge_base_repository: KnowledgeBaseRepository
    ) -> None:
        self._knowledge_base_repository = knowledge_base_repository

    async def execute(
        self,
        tenant_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[KnowledgeBase]:
        if tenant_id:
            return await self._knowledge_base_repository.find_all_by_tenant(
                tenant_id, limit=limit, offset=offset,
            )
        return await self._knowledge_base_repository.find_all(
            limit=limit, offset=offset,
        )

    async def count(self, tenant_id: str | None = None) -> int:
        if tenant_id:
            return await self._knowledge_base_repository.count_by_tenant(tenant_id)
        return await self._knowledge_base_repository.count_all()
