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


class ChunkRepository(ABC):
    @abstractmethod
    async def save_batch(self, chunks: list[Chunk]) -> None: ...

    @abstractmethod
    async def find_by_document(self, document_id: str) -> list[Chunk]: ...


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
