"""Wiki BC value objects."""

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class EdgeConfidence(str, Enum):
    """Edge confidence label — 表達關係的可信度。

    EXTRACTED  — 直接從原文擷取的關係
    INFERRED   — LLM 推論出的關係（帶 score）
    AMBIGUOUS  — 存疑，需人工審查
    """

    EXTRACTED = "EXTRACTED"
    INFERRED = "INFERRED"
    AMBIGUOUS = "AMBIGUOUS"


class WikiStatus(str, Enum):
    """Wiki graph 編譯狀態。"""

    PENDING = "pending"
    COMPILING = "compiling"
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"


@dataclass(frozen=True)
class WikiGraphId:
    value: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class WikiNodeId:
    value: str = field(default_factory=lambda: str(uuid4()))
