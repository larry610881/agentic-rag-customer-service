"""Shared fixtures & fakes for S-KB-Studio.1 BDD tests."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from src.domain.knowledge.entity import Chunk, ChunkCategory, Document, KnowledgeBase
from src.domain.knowledge.repository import (
    ChunkCategoryRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.knowledge.value_objects import ChunkId, DocumentId
from src.domain.rag.services import EmbeddingService, VectorStore
from src.domain.rag.value_objects import SearchResult


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FakeKbRepo(KnowledgeBaseRepository):
    def __init__(self) -> None:
        self.items: dict[str, KnowledgeBase] = {}

    async def save(self, knowledge_base: KnowledgeBase) -> None:
        self.items[knowledge_base.id] = knowledge_base

    async def find_by_id(self, kb_id: str) -> KnowledgeBase | None:
        return self.items.get(kb_id)

    async def find_all_by_tenant(
        self, tenant_id: str, *, limit=None, offset=None
    ) -> list[KnowledgeBase]:
        return [k for k in self.items.values() if k.tenant_id == tenant_id]

    async def find_all(self, *, tenant_id=None, limit=None, offset=None):
        result = list(self.items.values())
        if tenant_id:
            result = [k for k in result if k.tenant_id == tenant_id]
        return result

    async def count_by_tenant(self, tenant_id: str) -> int:
        return sum(1 for k in self.items.values() if k.tenant_id == tenant_id)

    async def count_all(self, *, tenant_id=None) -> int:
        if tenant_id:
            return await self.count_by_tenant(tenant_id)
        return len(self.items)

    async def find_system_kbs(self, tenant_id: str):
        return []

    async def update(self, kb_id: str, **fields) -> None:
        kb = self.items.get(kb_id)
        if kb:
            for k, v in fields.items():
                setattr(kb, k, v)

    async def delete(self, kb_id: str) -> None:
        self.items.pop(kb_id, None)


class FakeDocumentRepo(DocumentRepository):
    def __init__(self) -> None:
        self.docs: dict[str, Document] = {}
        self.chunks: dict[str, Chunk] = {}

    # Doc
    async def save(self, document: Document) -> None:
        self.docs[document.id.value] = document

    async def find_by_id(self, doc_id: str) -> Document | None:
        return self.docs.get(doc_id)

    async def find_by_ids(self, doc_ids):
        return [self.docs[d] for d in doc_ids if d in self.docs]

    async def find_all_by_kb(self, kb_id, *, limit=None, offset=None):
        return [d for d in self.docs.values() if d.kb_id == kb_id]

    async def find_top_level_by_kb(self, kb_id, *, limit=None, offset=None):
        return [
            d for d in self.docs.values()
            if d.kb_id == kb_id and getattr(d, "parent_id", None) is None
        ]

    async def count_by_kb(self, kb_id: str) -> int:
        return sum(1 for d in self.docs.values() if d.kb_id == kb_id)

    async def count_top_level_by_kb(self, kb_id: str) -> int:
        return await self.count_by_kb(kb_id)

    async def count_by_kb_status(self, kb_id, statuses):
        return sum(
            1 for d in self.docs.values()
            if d.kb_id == kb_id and getattr(d, "status", "") in statuses
        )

    async def update_status(self, doc_id, status, chunk_count=None): ...
    async def update_content(self, doc_id, content): ...
    async def delete(self, doc_id: str) -> None:
        self.docs.pop(doc_id, None)

    async def update_storage_path(self, doc_id, storage_path): ...
    async def update_quality(self, doc_id, **kw): ...

    # Chunks
    async def save_chunks(self, chunks):
        for c in chunks:
            self.chunks[c.id.value] = c

    async def delete_chunks_by_document(self, document_id):
        for cid in list(self.chunks):
            if self.chunks[cid].document_id == document_id:
                self.chunks.pop(cid)

    async def find_chunks_by_document_paginated(
        self, document_id, limit=20, offset=0
    ):
        return [
            c for c in self.chunks.values() if c.document_id == document_id
        ][offset : offset + limit]

    async def count_chunks_by_document(self, document_id: str) -> int:
        return sum(
            1 for c in self.chunks.values() if c.document_id == document_id
        )

    async def find_chunk_ids_by_kb(self, kb_id):
        doc_ids = {d.id.value for d in self.docs.values() if d.kb_id == kb_id}
        return {
            d: [c.id.value for c in self.chunks.values() if c.document_id == d]
            for d in doc_ids
        }

    async def update_chunks_category(self, chunk_ids, category_id):
        for cid in chunk_ids:
            if cid in self.chunks:
                self.chunks[cid].category_id = category_id

    async def find_chunks_by_category(self, category_id):
        return [c for c in self.chunks.values() if c.category_id == category_id]

    async def find_max_updated_at_by_kb(self, kb_id, tenant_id):
        return None

    async def find_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        return self.chunks.get(chunk_id)

    async def update_chunk(
        self, chunk_id, *, content=None, context_text=None
    ) -> None:
        if content is None and context_text is None:
            raise ValueError("at least one required")
        c = self.chunks.get(chunk_id)
        if c is None:
            return
        if content is not None:
            c.content = content
        if context_text is not None:
            c.context_text = context_text

    async def delete_chunk(self, chunk_id: str) -> None:
        self.chunks.pop(chunk_id, None)

    async def find_chunks_by_kb_paginated(
        self, kb_id, *, page=1, page_size=50, category_id=None
    ):
        doc_ids = {d.id.value for d in self.docs.values() if d.kb_id == kb_id}
        kb_chunks = [
            c for c in self.chunks.values() if c.document_id in doc_ids
        ]
        if category_id is not None:
            kb_chunks = [c for c in kb_chunks if c.category_id == category_id]
        offset = max(0, (page - 1) * page_size)
        return kb_chunks[offset : offset + page_size]

    async def count_chunks_by_kb(self, kb_id, *, category_id=None):
        doc_ids = {d.id.value for d in self.docs.values() if d.kb_id == kb_id}
        count = sum(1 for c in self.chunks.values() if c.document_id in doc_ids)
        if category_id is not None:
            count = sum(
                1
                for c in self.chunks.values()
                if c.document_id in doc_ids and c.category_id == category_id
            )
        return count


class FakeCategoryRepo(ChunkCategoryRepository):
    def __init__(self) -> None:
        self.items: dict[str, ChunkCategory] = {}

    async def save(self, category: ChunkCategory) -> None:
        self.items[category.id] = category

    async def save_batch(self, categories):
        for c in categories:
            self.items[c.id] = c

    async def find_by_kb(self, kb_id):
        return [c for c in self.items.values() if c.kb_id == kb_id]

    async def find_by_id(self, cat_id):
        return self.items.get(cat_id)

    async def update_name(self, cat_id, name):
        if cat_id in self.items:
            self.items[cat_id].name = name

    async def delete_by_kb(self, kb_id):
        for cid in list(self.items):
            if self.items[cid].kb_id == kb_id:
                self.items.pop(cid)

    async def update_chunk_counts(self, kb_id):
        pass

    async def delete_by_id(self, category_id: str) -> None:
        self.items.pop(category_id, None)

    async def assign_chunks(self, category_id, chunk_ids):
        # 記錄呼叫，真的寫 chunk.category_id 由 FakeDocRepo 另一 fixture 處理
        self.last_assigned = (category_id, list(chunk_ids))


class FakeArqPool:
    """Mock arq pool; 記錄 enqueue 動作"""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple, dict]] = []

    async def enqueue_job(self, job_name: str, *args, **kwargs):
        self.jobs.append((job_name, args, kwargs))
        return None


class FakeVectorStore(VectorStore):
    def __init__(self) -> None:
        self.upserts: list[tuple[str, list[str], list[list[float]], list[dict]]] = []
        self.single_upserts: list[tuple[str, str, list[float], dict]] = []
        self.deletes: list[tuple[str, dict]] = []
        self.search_results: list[SearchResult] = []
        self.collections_info: list[dict[str, Any]] = []
        self.stats_by_col: dict[str, dict[str, Any]] = {}
        self.delete_should_fail = False

    async def upsert(self, collection, ids, vectors, payloads):
        self.upserts.append((collection, list(ids), list(vectors), list(payloads)))

    async def ensure_collection(self, collection, vector_size): ...

    async def search(
        self, collection, query_vector, limit=5, score_threshold=0.3, filters=None
    ):
        return list(self.search_results[:limit])

    async def delete(self, collection, filters):
        if self.delete_should_fail:
            raise RuntimeError("simulated milvus delete failure")
        self.deletes.append((collection, dict(filters)))

    async def upsert_single(self, collection, id, vector, payload):
        self.single_upserts.append((collection, id, list(vector), dict(payload)))

    async def list_collections(self):
        return list(self.collections_info)

    async def get_collection_stats(self, collection):
        return self.stats_by_col.get(collection, {})


class FakeEmbeddingService(EmbeddingService):
    model_name = "fake-embed"

    def __init__(self) -> None:
        self.calls = 0
        self.should_fail = False

    async def embed_texts(self, texts):
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("simulated embedding failure")
        return [[0.1] * 3072 for _ in texts]

    async def embed_query(self, text):
        if self.should_fail:
            raise RuntimeError("simulated embedding failure")
        return [0.1] * 3072


def make_kb(kb_id: str, tenant_id: str = "T001") -> KnowledgeBase:
    return KnowledgeBase(id=kb_id, tenant_id=tenant_id, name=f"kb-{kb_id}")


def make_doc(doc_id: str, kb_id: str, tenant_id: str = "T001") -> Document:
    return Document(
        id=DocumentId(value=doc_id),
        kb_id=kb_id,
        tenant_id=tenant_id,
        filename=f"{doc_id}.pdf",
        content_type="pdf",
        status="processed",
    )


def make_chunk(
    chunk_id: str,
    document_id: str,
    tenant_id: str = "T001",
    content: str = "內容",
    category_id: str | None = None,
    quality_flag: str | None = None,
) -> Chunk:
    return Chunk(
        id=ChunkId(value=chunk_id),
        document_id=document_id,
        tenant_id=tenant_id,
        content=content,
        context_text="",
        chunk_index=0,
        category_id=category_id,
        quality_flag=quality_flag,
    )
