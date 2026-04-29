"""刪除知識庫用例"""

from src.application.knowledge._admin_kb_check import ensure_kb_accessible
from src.domain.knowledge.repository import DocumentRepository, KnowledgeBaseRepository
from src.domain.rag.services import VectorStore


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

    async def execute(self, kb_id: str, requester_tenant_id: str = "") -> None:
        # 之前完全無 tenant 檢查 → 任意 tenant 可刪任意 KB（CRITICAL）
        await ensure_kb_accessible(self._kb_repo, kb_id, requester_tenant_id)

        # 1) 查出所有 document
        documents = await self._doc_repo.find_all_by_kb(kb_id)

        # 2) 逐 doc 刪除 Milvus 向量
        for doc in documents:
            await self._vector_store.delete(
                collection=f"kb_{kb_id}",
                filters={"document_id": doc.id.value},
            )

        # 3) 刪除 DB（級聯：chunks → documents → knowledge_base）
        await self._kb_repo.delete(kb_id)
