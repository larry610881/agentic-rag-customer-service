from src.domain.knowledge.repository import DocumentRepository
from src.domain.knowledge.services import DocumentFileStorageService
from src.domain.rag.services import VectorStore
from src.domain.shared.exceptions import EntityNotFoundError
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


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

        # CASCADE: 找出所有 child documents（PDF 拆頁產生的子頁），它們的
        # 檔案 / Milvus chunks / DB row 必須跟著父一起刪。否則父刪了但 child
        # 與其向量殘留 → carrefour 觀察到的「刪除的 DM 還會被搜出來」bug
        # （root cause）。
        children = await self._doc_repo.find_children(doc_id)
        all_doc_ids = [doc_id] + [c.id.value for c in children]

        # 1. 刪所有 children + 父 的檔案 storage
        for d in [doc, *children]:
            if d.storage_path:
                try:
                    await self._file_storage.delete(d.storage_path)
                except FileNotFoundError:
                    pass
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "document.delete.storage_failed",
                        doc_id=d.id.value,
                        storage_path=d.storage_path,
                    )

        # 2. 刪 Milvus 向量 — 一次 IN list 把父 + 所有 children 都清掉
        # （MilvusVectorStore._build_filter_expr 支援 list value → IN operator）
        try:
            await self._vector_store.delete(
                collection=f"kb_{kb_id}",
                filters={"document_id": all_doc_ids},
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "document.delete.milvus_failed",
                kb_id=kb_id,
                doc_ids=all_doc_ids,
                exc_info=True,
            )

        # 3. 刪 DB record（先 children 再父，避免 FK 衝突）
        for child in children:
            await self._doc_repo.delete(child.id.value)
        await self._doc_repo.delete(doc_id)

        logger.info(
            "document.delete.cascade",
            parent_id=doc_id,
            children_count=len(children),
            kb_id=kb_id,
            tenant_id=tenant_id,
        )

        # Clear old categories first, then re-classify if KB still has docs
        try:
            from sqlalchemy import delete

            from src.infrastructure.db.engine import async_session_factory
            from src.infrastructure.db.models.chunk_category_model import (
                ChunkCategoryModel,
            )

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
