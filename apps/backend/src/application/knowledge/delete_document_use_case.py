"""刪除知識庫文件用例（Phase C — 透過 Outbox Pattern）

修正點（接續 Phase B DeleteKnowledgeBase）：
- vector_store.delete 直接呼叫 → publish vector.delete outbox 事件
- filters 帶父 + 所有 children 的 document_id（IN list 一次 cascade）
- doc_watermark_ts = parent doc.created_at → drain 時 id-reuse guard

保持 in-band（不走 outbox）的副作用：
- Storage delete（檔案系統，本身就比較可靠 + 不影響 RAG 一致性）
- chunk_category clear + classify_kb re-enqueue（DB only，failure 不破壞 RAG）

Atomicity：use case 不持有 session（DDD 紅線）。publish session.add 不 commit；
後續 doc_repo.delete 內 atomic() 帶上 publish 一起 commit。任一 raise
SAVEPOINT rollback 把 publish 也丟掉。
"""

from src.application.outbox.publish_outbox_event_use_case import (
    PublishOutboxEventUseCase,
)
from src.domain.knowledge.repository import DocumentRepository
from src.domain.knowledge.services import DocumentFileStorageService
from src.domain.outbox.events import vector_delete_event
from src.domain.shared.exceptions import EntityNotFoundError
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class DeleteDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepository,
        publish_outbox_event_use_case: PublishOutboxEventUseCase,
        document_file_storage: DocumentFileStorageService,
    ) -> None:
        self._doc_repo = document_repository
        self._publish_outbox = publish_outbox_event_use_case
        self._file_storage = document_file_storage

    async def execute(self, doc_id: str) -> None:
        doc = await self._doc_repo.find_by_id(doc_id)
        if doc is None:
            raise EntityNotFoundError("Document", doc_id)

        kb_id = doc.kb_id
        tenant_id = doc.tenant_id

        # CASCADE: 找出所有 child documents（PDF 拆頁產生的子頁），它們的
        # 檔案 / Milvus chunks / DB row 必須跟著父一起刪。
        children = await self._doc_repo.find_children(doc_id)
        all_doc_ids = [doc_id] + [c.id.value for c in children]

        # 1. 刪所有 children + 父 的檔案 storage（in-band；失敗 log 不擋）
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

        # 2. Publish outbox vector.delete 事件 — drain 後對 Milvus 套用
        # filters 帶父 + 所有 children 的 document_id list（IN operator）
        # doc_watermark_ts 給 drain 端的 id-reuse guard 用
        event = vector_delete_event(
            tenant_id=tenant_id,
            aggregate_type="document",
            aggregate_id=doc_id,
            collection=f"kb_{kb_id}",
            filters={"document_id": all_doc_ids},
            doc_watermark_ts=doc.created_at,
        )
        await self._publish_outbox.execute(event)

        # 3. PG cascade delete（先 children 再父，避免 FK 衝突）
        # doc_repo.delete 內 atomic commit 會帶上 publish 的 INSERT 一起持久化
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

        # 4. Clear old categories + re-classify（in-band；失敗不影響 RAG）
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
        except Exception:  # noqa: BLE001
            pass

        # Re-classify if there are remaining documents
        try:
            remaining = await self._doc_repo.count_by_kb(kb_id)
            if remaining > 0:
                from src.infrastructure.queue.arq_pool import enqueue
                await enqueue("classify_kb", kb_id, tenant_id)
        except Exception:  # noqa: BLE001
            pass
