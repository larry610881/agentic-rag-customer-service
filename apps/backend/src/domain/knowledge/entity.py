from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.knowledge.value_objects import (
    ChunkId,
    DocumentId,
    KnowledgeBaseId,
    ProcessingTaskId,
)


@dataclass
class KnowledgeBase:
    id: KnowledgeBaseId = field(default_factory=KnowledgeBaseId)
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    kb_type: str = "user"  # "user" | "system"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class Document:
    id: DocumentId = field(default_factory=DocumentId)
    kb_id: str = ""
    tenant_id: str = ""
    filename: str = ""
    content_type: str = ""
    content: str = ""
    status: str = "pending"
    chunk_count: int = 0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class Chunk:
    id: ChunkId = field(default_factory=ChunkId)
    document_id: str = ""
    tenant_id: str = ""
    content: str = ""
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class ProcessingTask:
    id: ProcessingTaskId = field(default_factory=ProcessingTaskId)
    document_id: str = ""
    tenant_id: str = ""
    status: str = "pending"
    progress: int = 0
    error_message: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
