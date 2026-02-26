from abc import ABC, abstractmethod

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.value_objects import QualityScore


class FileParserService(ABC):
    @abstractmethod
    def parse(self, raw_bytes: bytes, content_type: str) -> str: ...

    @abstractmethod
    def supported_types(self) -> set[str]: ...


class TextSplitterService(ABC):
    @abstractmethod
    def split(
        self,
        text: str,
        document_id: str,
        tenant_id: str,
        content_type: str = "",
    ) -> list[Chunk]: ...


class ChunkQualityService:
    """Pure-function Domain Service for calculating chunk quality scores."""

    SHORT_THRESHOLD = 50
    SHORT_RATIO_LIMIT = 0.2
    VARIANCE_RATIO_LIMIT = 3.0
    MID_SENTENCE_RATIO_LIMIT = 0.3
    SENTENCE_ENDINGS = (".", "。", "!", "！", "?", "？", "\n")

    @classmethod
    def calculate(cls, chunks: list[Chunk]) -> QualityScore:
        if not chunks:
            return QualityScore()

        lengths = [len(c.content) for c in chunks]
        avg_len = sum(lengths) // len(lengths)
        min_len = min(lengths)
        max_len = max(lengths)

        score = 1.0
        issues: list[str] = []

        # too_short: >20% chunks < 50 chars
        short_count = sum(1 for ln in lengths if ln < cls.SHORT_THRESHOLD)
        if short_count / len(lengths) > cls.SHORT_RATIO_LIMIT:
            score -= 0.3
            issues.append("too_short")

        # high_variance: max/avg > 3.0
        if avg_len > 0 and max_len / avg_len > cls.VARIANCE_RATIO_LIMIT:
            score -= 0.2
            issues.append("high_variance")

        # mid_sentence_break: >30% chunks don't end with sentence-ending punctuation
        mid_sentence_count = sum(
            1 for c in chunks if not c.content.rstrip().endswith(cls.SENTENCE_ENDINGS)
        )
        if mid_sentence_count / len(chunks) > cls.MID_SENTENCE_RATIO_LIMIT:
            score -= 0.2
            issues.append("mid_sentence_break")

        return QualityScore(
            score=max(score, 0.0),
            avg_chunk_length=avg_len,
            min_chunk_length=min_len,
            max_chunk_length=max_len,
            issues=tuple(issues),
        )
