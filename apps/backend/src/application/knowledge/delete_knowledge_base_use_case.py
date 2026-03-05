"""刪除知識庫用例"""

from src.domain.knowledge.repository import DocumentRepository, KnowledgeBaseRepository
from src.domain.rag.services import VectorStore
from src.domain.shared.exceptions import EntityNotFoundError


class DeleteKnowledgeBaseUseCase:
    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
        vector_store: VectorStore,
    ) -> None:
        self._kb_repo = knowledge_base_repository
        self._doc_repo = document_repository
        self._vector_store = vector_store

    async def execute(self, kb_id: str) -> None:
        kb = await self._kb_repo.find_by_id(kb_id)
        if kb is None:
            raise EntityNotFoundError("KnowledgeBase", kb_id)

        # 1) 查出所有 document
        documents = await self._doc_repo.find_all_by_kb(kb_id)

        # 2) 逐 doc 刪除 Qdrant 向量
        for doc in documents:
            await self._vector_store.delete(
                collection=f"kb_{kb_id}",
                filters={"document_id": doc.id.value},
            )

        # 3) 刪除 DB（級聯：chunks → documents → knowledge_base）
        await self._kb_repo.delete(kb_id)
