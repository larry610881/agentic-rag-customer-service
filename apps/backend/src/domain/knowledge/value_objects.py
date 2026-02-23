from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class KnowledgeBaseId:
    value: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class DocumentId:
    value: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class ChunkId:
    value: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class ProcessingTaskId:
    value: str = field(default_factory=lambda: str(uuid4()))
