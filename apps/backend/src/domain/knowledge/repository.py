from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.knowledge.entity import Chunk, Document, KnowledgeBase, ProcessingTask


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
    async def find_all_by_kb(
        self,
        kb_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Document]: ...

    @abstractmethod
    async def count_by_kb(self, kb_id: str) -> int: ...

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
    async def find_max_updated_at_by_kb(
        self, kb_id: str, tenant_id: str
    ) -> datetime | None:
        """Return the latest document.updated_at in a KB for stale detection.

        Used by Wiki status query to determine if knowledge base has been
        modified since wiki graph was compiled. Returns None if KB has no
        documents.
        """
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
