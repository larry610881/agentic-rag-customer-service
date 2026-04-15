from dataclasses import dataclass

from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class UpdateKnowledgeBaseCommand:
    kb_id: str
    name: str | None = None
    description: str | None = None
    ocr_mode: str | None = None
    ocr_model: str | None = None
    context_model: str | None = None
    classification_model: str | None = None


class UpdateKnowledgeBaseUseCase:
    def __init__(
        self, knowledge_base_repository: KnowledgeBaseRepository
    ) -> None:
        self._repo = knowledge_base_repository

    async def execute(self, command: UpdateKnowledgeBaseCommand) -> None:
        kb = await self._repo.find_by_id(command.kb_id)
        if kb is None:
            raise EntityNotFoundError("KnowledgeBase", command.kb_id)
        fields = {
            k: v
            for k, v in {
                "name": command.name,
                "description": command.description,
                "ocr_mode": command.ocr_mode,
                "ocr_model": command.ocr_model,
                "context_model": command.context_model,
                "classification_model": command.classification_model,
            }.items()
            if v is not None
        }
        if fields:
            await self._repo.update(command.kb_id, **fields)
