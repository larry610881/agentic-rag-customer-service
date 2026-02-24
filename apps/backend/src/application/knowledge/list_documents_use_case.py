from src.domain.knowledge.entity import Document
from src.domain.knowledge.repository import DocumentRepository


class ListDocumentsUseCase:
    def __init__(self, document_repository: DocumentRepository) -> None:
        self._doc_repo = document_repository

    async def execute(self, kb_id: str) -> list[Document]:
        return await self._doc_repo.find_all_by_kb(kb_id)
