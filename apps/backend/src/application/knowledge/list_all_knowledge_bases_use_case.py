from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.repository import KnowledgeBaseRepository


class ListAllKnowledgeBasesUseCase:
    def __init__(
        self, knowledge_base_repository: KnowledgeBaseRepository
    ) -> None:
        self._knowledge_base_repository = knowledge_base_repository

    async def execute(self) -> list[KnowledgeBase]:
        return await self._knowledge_base_repository.find_all()
