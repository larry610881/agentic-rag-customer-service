from dataclasses import dataclass

from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.knowledge.value_objects import KnowledgeBaseId


@dataclass(frozen=True)
class CreateKnowledgeBaseCommand:
    tenant_id: str
    name: str
    description: str = ""


class CreateKnowledgeBaseUseCase:
    def __init__(
        self, knowledge_base_repository: KnowledgeBaseRepository
    ) -> None:
        self._knowledge_base_repository = knowledge_base_repository

    async def execute(self, command: CreateKnowledgeBaseCommand) -> KnowledgeBase:
        kb = KnowledgeBase(
            id=KnowledgeBaseId(),
            tenant_id=command.tenant_id,
            name=command.name,
            description=command.description,
        )
        await self._knowledge_base_repository.save(kb)
        return kb
