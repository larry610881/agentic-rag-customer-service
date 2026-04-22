"""Classify all chunks in a KB using embedding clustering + LLM naming.

Orchestrates: fetch chunks/vectors → cluster → name → save categories → assign chunks.
Runs as arq background job.
"""

from typing import TYPE_CHECKING

from src.domain.knowledge.repository import (
    ChunkCategoryRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.rag.services import VectorStore
from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.category import UsageCategory
from src.infrastructure.classification.cluster_classification_service import (
    ClusterClassificationService,
)
from src.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from src.application.usage.record_usage_use_case import RecordUsageUseCase

logger = get_logger(__name__)


class ClassifyKbUseCase:
    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
        category_repository: ChunkCategoryRepository,
        vector_store: VectorStore,
        classification_service: ClusterClassificationService,
        record_usage: "RecordUsageUseCase | None" = None,
    ) -> None:
        self._kb_repo = knowledge_base_repository
        self._doc_repo = document_repository
        self._cat_repo = category_repository
        self._vector_store = vector_store
        self._classification = classification_service
        self._record_usage = record_usage

    async def execute(self, kb_id: str, tenant_id: str) -> None:
        log = logger.bind(kb_id=kb_id, tenant_id=tenant_id)
        log.info("classify_kb.start")

        kb = await self._kb_repo.find_by_id(kb_id)
        if kb is None:
            log.warning("classify_kb.kb_not_found")
            return

        # 1. Get all chunk IDs in this KB
        chunk_ids_by_doc = await self._doc_repo.find_chunk_ids_by_kb(kb_id)
        all_chunk_ids: list[str] = []
        for doc_chunks in chunk_ids_by_doc.values():
            all_chunk_ids.extend(doc_chunks)

        if not all_chunk_ids:
            log.info("classify_kb.no_chunks")
            return

        # 2. Fetch vectors from Milvus
        collection = f"kb_{kb_id}"
        try:
            results = await self._vector_store.fetch_vectors(
                collection, all_chunk_ids
            )
        except Exception:
            log.warning("classify_kb.fetch_vectors_failed", exc_info=True)
            return

        if not results:
            log.info("classify_kb.no_vectors")
            return

        # results: list of (id, vector, payload)
        fetched_ids = [r[0] for r in results]
        fetched_vectors = [r[1] for r in results]
        fetched_contents = [r[2].get("content", "") for r in results]

        # 3. Classify — resolve model: KB → tenant default → hardcode
        classification_model = getattr(kb, "classification_model", "")
        if not classification_model:
            try:
                from sqlalchemy import select

                from src.infrastructure.db.engine import async_session_factory
                from src.infrastructure.db.models.tenant_model import TenantModel
                async with async_session_factory() as session:
                    stmt = select(TenantModel.default_classification_model).where(
                        TenantModel.id == tenant_id
                    )
                    result = await session.execute(stmt)
                    classification_model = result.scalar_one_or_none() or ""
            except Exception:
                pass
        categories, chunk_to_cat = await self._classification.classify(
            chunk_ids=fetched_ids,
            chunk_contents=fetched_contents,
            vectors=fetched_vectors,
            kb_id=kb_id,
            tenant_id=tenant_id,
            model=classification_model,
        )

        if not categories:
            log.info("classify_kb.no_categories_generated")
            return

        # Token-Gov.0: 記錄 auto-classification token 用量
        # S-LLM-Cache.1: 加上 cache_read / cache_creation 欄位
        # Session refresh fix：LLM 長時間呼叫後 ContextVar session 可能已超時
        # （asyncpg idle 或 PG idle_in_transaction_session_timeout）；refresh
        # 一個新 session 給 record_usage 用，避免 silently 寫不進 DB。
        if self._record_usage and (
            self._classification.last_input_tokens
            + self._classification.last_output_tokens
        ) > 0:
            try:
                from src.infrastructure.db.engine import async_session_factory
                _new_session = async_session_factory()
                if (
                    hasattr(self._record_usage, "_repo")
                    and hasattr(self._record_usage._repo, "_session")
                ):
                    self._record_usage._repo._session = _new_session
            except Exception:
                pass

            cls_in = self._classification.last_input_tokens
            cls_out = self._classification.last_output_tokens
            cls_cache_read = getattr(
                self._classification, "last_cache_read_tokens", 0
            )
            cls_cache_creation = getattr(
                self._classification, "last_cache_creation_tokens", 0
            )
            await self._record_usage.execute(
                tenant_id=tenant_id,
                request_type=UsageCategory.AUTO_CLASSIFICATION.value,
                usage=TokenUsage(
                    model=self._classification.last_model,
                    input_tokens=cls_in,
                    output_tokens=cls_out,
                    total_tokens=cls_in + cls_out,
                    cache_read_tokens=cls_cache_read,
                    cache_creation_tokens=cls_cache_creation,
                ),
            )

        # 4. Delete old categories
        await self._cat_repo.delete_by_kb(kb_id)

        # 5. Save new categories
        await self._cat_repo.save_batch(categories)

        # 6. Assign chunks to categories (use independent session)
        from sqlalchemy import update

        from src.infrastructure.db.engine import async_session_factory
        from src.infrastructure.db.models.chunk_model import ChunkModel

        async with async_session_factory() as session:
            for cat in categories:
                chunk_ids_for_cat = [
                    cid for cid, cat_id in chunk_to_cat.items()
                    if cat_id == cat.id
                ]
                if chunk_ids_for_cat:
                    await session.execute(
                        update(ChunkModel)
                        .where(ChunkModel.id.in_(chunk_ids_for_cat))
                        .values(category_id=cat.id)
                    )
            await session.commit()

        # 7. Update counts
        await self._cat_repo.update_chunk_counts(kb_id)

        log.info(
            "classify_kb.done",
            categories=len(categories),
            classified_chunks=len(chunk_to_cat),
        )
