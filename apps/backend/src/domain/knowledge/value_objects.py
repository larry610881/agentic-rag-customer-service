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


@dataclass
class OcrUsageTally:
    """單次文件 OCR 的用量累計（Issue #78）。

    每個 use case 執行各自建立一份並沿呼叫鏈往下傳，取代引擎上的
    ``last_*`` 共用計數器，並行處理的文件之間不會互相污染。
    ``model`` 為實際使用的 ``provider:model`` spec。
    """

    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""

    def add(self, input_tokens: int, output_tokens: int, model: str = "") -> None:
        self.input_tokens += max(int(input_tokens), 0)
        self.output_tokens += max(int(output_tokens), 0)
        if model:
            self.model = model

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
