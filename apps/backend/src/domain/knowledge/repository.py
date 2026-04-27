from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.knowledge.entity import (
    Chunk,
    ChunkCategory,
    Document,
    KnowledgeBase,
    ProcessingTask,
)


class KnowledgeBaseRepository(ABC):
    @abstractmethod
    async def save(self, knowledge_base: KnowledgeBase) -> None: ...

    @abstractmethod
    async def find_by_id(self, kb_id: str) -> KnowledgeBase | None: ...

    @abstractmethod
    async def find_all_by_tenant(
        self,
        tenant_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[KnowledgeBase]: ...

    @abstractmethod
    async def find_all(
        self,
        *,
        tenant_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[KnowledgeBase]: ...

    @abstractmethod
    async def count_by_tenant(self, tenant_id: str) -> int: ...

    @abstractmethod
    async def count_all(
        self, *, tenant_id: str | None = None
    ) -> int: ...

    @abstractmethod
    async def find_system_kbs(
        self, tenant_id: str
    ) -> list[KnowledgeBase]: ...

    @abstractmethod
    async def update(self, kb_id: str, **fields: object) -> None: ...

    @abstractmethod
    async def delete(self, kb_id: str) -> None: ...


class DocumentRepository(ABC):
    # --- Document methods ---

    @abstractmethod
    async def save(self, document: Document) -> None: ...

    @abstractmethod
    async def find_by_id(self, doc_id: str) -> Document | None: ...

    @abstractmethod
    async def find_by_ids(self, doc_ids: list[str]) -> list[Document]:
        """Batch 查詢多份文件，避免 N+1 query。空 list 直接回 []。"""
        ...

    @abstractmethod
    async def find_all_by_kb(
        self,
        kb_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Document]: ...

    @abstractmethod
    async def find_top_level_by_kb(
        self,
        kb_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Document]:
        """只回傳 top-level documents (parent_id IS NULL)，用於 UI 列表分頁。"""
        ...

    @abstractmethod
    async def count_by_kb(self, kb_id: str) -> int: ...

    @abstractmethod
    async def count_top_level_by_kb(self, kb_id: str) -> int:
        """只算 top-level documents (parent_id IS NULL)，用於 UI 分頁總數。"""
        ...

    @abstractmethod
    async def count_by_kb_status(
        self, kb_id: str, statuses: list[str]
    ) -> int: ...

    @abstractmethod
    async def update_status(
        self, doc_id: str, status: str, chunk_count: int | None = None
    ) -> None: ...

    @abstractmethod
    async def update_content(
        self, doc_id: str, content: str
    ) -> None: ...

    @abstractmethod
    async def delete(self, doc_id: str) -> None: ...

    @abstractmethod
    async def update_storage_path(
        self, doc_id: str, storage_path: str
    ) -> None: ...

    @abstractmethod
    async def update_quality(
        self,
        doc_id: str,
        quality_score: float,
        avg_chunk_length: int,
        min_chunk_length: int,
        max_chunk_length: int,
        quality_issues: list[str],
    ) -> None: ...

    # --- Chunk methods (aggregate internal Entity) ---

    @abstractmethod
    async def save_chunks(self, chunks: list[Chunk]) -> None: ...

    @abstractmethod
    async def delete_chunks_by_document(self, document_id: str) -> None: ...

    @abstractmethod
    async def find_chunks_by_document_paginated(
        self, document_id: str, limit: int = 20, offset: int = 0
    ) -> list[Chunk]: ...

    @abstractmethod
    async def count_chunks_by_document(self, document_id: str) -> int: ...

    @abstractmethod
    async def find_chunk_ids_by_kb(
        self, kb_id: str
    ) -> dict[str, list[str]]: ...

    @abstractmethod
    async def update_chunks_category(
        self, chunk_ids: list[str], category_id: str | None
    ) -> None: ...

    @abstractmethod
    async def find_chunks_by_category(
        self, category_id: str
    ) -> list[Chunk]: ...

    @abstractmethod
    async def find_max_updated_at_by_kb(
        self, kb_id: str, tenant_id: str
    ) -> datetime | None:
        """Return the latest document.updated_at in a KB for stale detection.

        Returns None if KB has no documents.
        """
        ...

    # --- S-KB-Studio.1 新增：single-chunk + KB-level chunk 操作 ---

    @abstractmethod
    async def find_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        """單一 chunk 查詢（for KB Studio inline edit）。"""
        ...

    @abstractmethod
    async def update_chunk(
        self,
        chunk_id: str,
        *,
        content: str | None = None,
        context_text: str | None = None,
    ) -> None:
        """更新單 chunk content 與 / 或 context_text，自動更新 updated_at。

        至少需要一個非 None 欄位，否則 raise ValueError。
        """
        ...

    @abstractmethod
    async def delete_chunk(self, chunk_id: str) -> None:
        """刪除單一 chunk (不級聯刪 category)。"""
        ...

    @abstractmethod
    async def find_chunks_by_kb_paginated(
        self,
        kb_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
        category_id: str | None = None,
    ) -> list[Chunk]:
        """KB-level 分頁（跨文件），可選 category filter。"""
        ...

    @abstractmethod
    async def count_chunks_by_kb(
        self,
        kb_id: str,
        *,
        category_id: str | None = None,
    ) -> int:
        """KB-level chunk 總數（可選 category filter）。"""
        ...


class ProcessingTaskRepository(ABC):
    @abstractmethod
    async def save(self, task: ProcessingTask) -> None: ...

    @abstractmethod
    async def find_by_id(self, task_id: str) -> ProcessingTask | None: ...

    @abstractmethod
    async def update_status(
        self,
        task_id: str,
        status: str,
        progress: int | None = None,
        error_message: str | None = None,
    ) -> None: ...


class ChunkCategoryRepository(ABC):
    @abstractmethod
    async def save(self, category: ChunkCategory) -> None: ...

    @abstractmethod
    async def save_batch(self, categories: list[ChunkCategory]) -> None: ...

    @abstractmethod
    async def find_by_kb(self, kb_id: str) -> list[ChunkCategory]: ...

    @abstractmethod
    async def find_by_id(self, category_id: str) -> ChunkCategory | None: ...

    @abstractmethod
    async def update_name(self, category_id: str, name: str) -> None: ...

    @abstractmethod
    async def delete_by_kb(self, kb_id: str) -> None: ...

    @abstractmethod
    async def update_chunk_counts(self, kb_id: str) -> None:
        """Recalculate chunk_count for all categories in a KB."""
        ...

    # --- S-KB-Studio.1 新增：CRUD ---

    @abstractmethod
    async def delete_by_id(self, category_id: str) -> None:
        """刪除單一 category (chunks.category_id 級聯設 NULL 由 DB constraint 處理)。"""
        ...

    @abstractmethod
    async def assign_chunks(
        self, category_id: str, chunk_ids: list[str]
    ) -> None:
        """批次把多個 chunks 指派到某 category。

        對映至既有 DocumentRepository.update_chunks_category()，但入口在 category
        layer 以便 audit log 維度對齊 category-centric 操作。
        """
        ...
