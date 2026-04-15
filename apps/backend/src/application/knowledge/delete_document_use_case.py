from src.domain.knowledge.repository import DocumentRepository
from src.domain.knowledge.services import DocumentFileStorageService
from src.domain.rag.services import VectorStore
from src.domain.shared.exceptions import EntityNotFoundError


class DeleteDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepository,
        vector_store: VectorStore,
        document_file_storage: DocumentFileStorageService,
    ) -> None:
        self._doc_repo = document_repository
        self._vector_store = vector_store
        self._file_storage = document_file_storage

    async def execute(self, doc_id: str) -> None:
        doc = await self._doc_repo.find_by_id(doc_id)
        if doc is None:
            raise EntityNotFoundError("Document", doc_id)

        kb_id = doc.kb_id
        tenant_id = doc.tenant_id

        # Delete file from storage
        if doc.storage_path:
            try:
                await self._file_storage.delete(doc.storage_path)
            except FileNotFoundError:
                pass

        # Delete vectors from Milvus
        await self._vector_store.delete(
            collection=f"kb_{kb_id}",
            filters={"document_id": doc_id},
        )

        # Delete document (and its chunks) from DB
        await self._doc_repo.delete(doc_id)

        # Clear old categories first, then re-classify if KB still has docs
        try:
            from src.infrastructure.db.engine import async_session_factory
            from src.infrastructure.db.models.chunk_category_model import (
                ChunkCategoryModel,
            )
            from sqlalchemy import delete

            async with async_session_factory() as session:
                await session.execute(
                    delete(ChunkCategoryModel).where(
                        ChunkCategoryModel.kb_id == kb_id
                    )
                )
                await session.commit()
        except Exception:
            pass

        # Re-classify if there are remaining documents
        try:
            remaining = await self._doc_repo.count_by_kb(kb_id)
            if remaining > 0:
                from src.infrastructure.queue.arq_pool import enqueue
                await enqueue("classify_kb", kb_id, tenant_id)
        except Exception:
            pass
