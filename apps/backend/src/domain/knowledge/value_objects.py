from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class QualityScore:
    score: float = 0.0
    avg_chunk_length: int = 0
    min_chunk_length: int = 0
    max_chunk_length: int = 0
    issues: tuple[str, ...] = ()


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
