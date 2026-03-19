from src.domain.knowledge.entity import Document
from src.domain.knowledge.repository import DocumentRepository


class ListDocumentsUseCase:
    def __init__(self, document_repository: DocumentRepository) -> None:
        self._doc_repo = document_repository

    async def execute(
        self,
        kb_id: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Document]:
        return await self._doc_repo.find_all_by_kb(
            kb_id, limit=limit, offset=offset,
        )

    async def count(self, kb_id: str) -> int:
        return await self._doc_repo.count_by_kb(kb_id)
