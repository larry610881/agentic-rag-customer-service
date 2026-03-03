from src.domain.knowledge.repository import DocumentRepository
from src.domain.rag.services import VectorStore
from src.domain.shared.exceptions import EntityNotFoundError


class DeleteDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepository,
        vector_store: VectorStore,
    ) -> None:
        self._doc_repo = document_repository
        self._vector_store = vector_store

    async def execute(self, doc_id: str) -> None:
        doc = await self._doc_repo.find_by_id(doc_id)
        if doc is None:
            raise EntityNotFoundError("Document", doc_id)

        # Delete vectors from Qdrant
        await self._vector_store.delete(
            collection=f"kb_{doc.kb_id}",
            filters={"document_id": doc_id},
        )

        # Delete document (and its chunks) from DB
        await self._doc_repo.delete(doc_id)
