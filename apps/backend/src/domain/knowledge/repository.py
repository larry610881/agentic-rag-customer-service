from abc import ABC, abstractmethod

from src.domain.knowledge.entity import Chunk, Document, KnowledgeBase, ProcessingTask


class KnowledgeBaseRepository(ABC):
    @abstractmethod
    async def save(self, knowledge_base: KnowledgeBase) -> None: ...

    @abstractmethod
    async def find_by_id(self, kb_id: str) -> KnowledgeBase | None: ...

    @abstractmethod
    async def find_all_by_tenant(
        self, tenant_id: str
    ) -> list[KnowledgeBase]: ...

    @abstractmethod
    async def find_system_kbs(
        self, tenant_id: str
    ) -> list[KnowledgeBase]: ...


class DocumentRepository(ABC):
    @abstractmethod
    async def save(self, document: Document) -> None: ...

    @abstractmethod
    async def find_by_id(self, doc_id: str) -> Document | None: ...

    @abstractmethod
    async def find_all_by_kb(self, kb_id: str) -> list[Document]: ...

    @abstractmethod
    async def update_status(
        self, doc_id: str, status: str, chunk_count: int | None = None
    ) -> None: ...

    @abstractmethod
    async def delete(self, doc_id: str) -> None: ...

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


class ChunkRepository(ABC):
    @abstractmethod
    async def save_batch(self, chunks: list[Chunk]) -> None: ...

    @abstractmethod
    async def find_by_document(self, document_id: str) -> list[Chunk]: ...

    @abstractmethod
    async def delete_by_document(self, document_id: str) -> None: ...

    @abstractmethod
    async def find_by_document_paginated(
        self, document_id: str, limit: int = 20, offset: int = 0
    ) -> list[Chunk]: ...

    @abstractmethod
    async def count_by_document(self, document_id: str) -> int: ...

    @abstractmethod
    async def find_chunk_ids_by_kb(
        self, kb_id: str
    ) -> dict[str, list[str]]: ...


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
