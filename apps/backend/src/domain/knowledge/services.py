from __future__ import annotations

import hashlib
import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass

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


class LanguageDetectionService(ABC):
    """Port for language detection — Infrastructure provides the adapter."""

    @abstractmethod
    def detect(self, text: str) -> str:
        """Return ISO 639-1 code (e.g. 'zh-cn', 'en', 'ja')."""


# ---------------------------------------------------------------------------
# Pure-function Domain Services (classmethod-based, no external deps)
# ---------------------------------------------------------------------------

_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
_HORIZONTAL_WS_RE = re.compile(r"[^\S\n]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CSV_TYPES = frozenset({
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
})


class TextPreprocessor:
    """Pure-function Domain Service: normalize + boilerplate removal."""

    @classmethod
    def preprocess(cls, text: str, content_type: str) -> str:
        text = cls._remove_boilerplate(text, content_type)
        if content_type in _CSV_TYPES:
            text = CSVCleaningService.clean(text)
        text = cls._normalize(text)
        return text

    @classmethod
    def _normalize(cls, text: str) -> str:
        text = unicodedata.normalize("NFC", text)
        text = _ZERO_WIDTH_RE.sub("", text)
        text = _HORIZONTAL_WS_RE.sub(" ", text)
        text = _MULTI_NEWLINE_RE.sub("\n\n", text)
        return text

    @classmethod
    def _remove_boilerplate(cls, text: str, content_type: str) -> str:
        if content_type == "application/pdf":
            return cls._remove_pdf_boilerplate(text)
        return text

    @classmethod
    def _remove_pdf_boilerplate(cls, text: str) -> str:
        pages = text.split("\f")
        if len(pages) < 3:
            return text

        # Detect lines appearing in >50% of pages → boilerplate
        from collections import Counter

        line_page_count: Counter[str] = Counter()
        for page in pages:
            unique_lines = {ln.strip() for ln in page.splitlines() if ln.strip()}
            for ln in unique_lines:
                line_page_count[ln] += 1

        threshold = len(pages) * 0.5
        boilerplate = {ln for ln, cnt in line_page_count.items() if cnt > threshold}

        cleaned_pages: list[str] = []
        for page in pages:
            lines = [
                ln for ln in page.splitlines() if ln.strip() not in boilerplate
            ]
            cleaned_pages.append("\n".join(lines))
        return "\n\n".join(p for p in cleaned_pages if p.strip())


class CSVCleaningService:
    """Pure-function Domain Service: clean CSV columns before splitting.

    - Drop noise columns: timestamps, IDs, URLs, foreign keys
    - Strip HTML tags from cell values
    - Detect all-numeric / structurally meaningless CSV
    """

    # Exact column names to drop (lowercase, stripped)
    _DROP_EXACT: frozenset[str] = frozenset({
        "id", "created_at", "updated_at", "deleted_at",
        "start_at", "end_at", "deadline_at",
        "created_user", "updated_user", "deleted_user",
        "is_online", "is_active", "is_deleted", "sort_order",
    })

    # Column name suffixes that indicate noise
    _DROP_SUFFIXES: tuple[str, ...] = ("_id", "_at", "_url", "_uri")

    # Column name substrings that indicate URL/image noise
    _DROP_CONTAINS: tuple[str, ...] = ("url", "uri", "img", "image", "thumbnail")

    @classmethod
    def clean(cls, text: str) -> str:
        import csv
        import io

        lines = text.split("\n")
        if len(lines) < 2:
            return text

        header_line = lines[0]
        headers = [h.strip().lower() for h in header_line.split(",")]

        # Identify columns to keep
        keep_indices: list[int] = []
        for i, h in enumerate(headers):
            if cls._should_drop(h):
                continue
            keep_indices.append(i)

        # If no columns survive, return original (let ChunkFilter handle it)
        if not keep_indices:
            return text

        # If all kept columns are identical to original, skip rebuild
        if len(keep_indices) == len(headers):
            # Still strip HTML from cells
            return cls._strip_html_from_csv(text)

        # Rebuild CSV with only kept columns + HTML stripped
        reader = csv.reader(io.StringIO(text))
        out_lines: list[str] = []
        for row in reader:
            kept = []
            for i in keep_indices:
                cell = row[i].strip() if i < len(row) else ""
                cell = _HTML_TAG_RE.sub("", cell).strip()
                kept.append(cell)
            out_lines.append(", ".join(kept))

        return "\n".join(out_lines)

    @classmethod
    def _should_drop(cls, header: str) -> bool:
        if header in cls._DROP_EXACT:
            return True
        if any(header.endswith(s) for s in cls._DROP_SUFFIXES):
            return True
        if any(s in header for s in cls._DROP_CONTAINS):
            return True
        return False

    @classmethod
    def _strip_html_from_csv(cls, text: str) -> str:
        """Strip HTML tags from all cells without changing columns."""
        import csv
        import io

        reader = csv.reader(io.StringIO(text))
        out_lines: list[str] = []
        for row in reader:
            cleaned = [_HTML_TAG_RE.sub("", cell).strip() for cell in row]
            out_lines.append(", ".join(cleaned))
        return "\n".join(out_lines)


@dataclass(frozen=True)
class FilterResult:
    accepted: list[Chunk]
    rejected_count: int
    rejection_reasons: dict[str, str]  # chunk_id → reason


_NOISE_PATTERN = re.compile(r"^[\s\W\d]+$")


class ChunkFilterService:
    """Pure-function Domain Service: reject bad chunks before embedding."""

    @classmethod
    def filter(
        cls, chunks: list[Chunk], *, min_length: int = 20
    ) -> FilterResult:
        accepted: list[Chunk] = []
        reasons: dict[str, str] = {}
        for chunk in chunks:
            stripped = chunk.content.strip()
            if len(stripped) < min_length:
                reasons[chunk.id.value] = "too_short"
                continue
            if _NOISE_PATTERN.match(stripped):
                reasons[chunk.id.value] = "noise_only"
                continue
            accepted.append(chunk)
        return FilterResult(
            accepted=accepted,
            rejected_count=len(reasons),
            rejection_reasons=reasons,
        )


class ChunkDeduplicationService:
    """Pure-function Domain Service: exact dedup via content hash."""

    @classmethod
    def deduplicate(cls, chunks: list[Chunk]) -> list[Chunk]:
        seen: set[str] = set()
        result: list[Chunk] = []
        for chunk in chunks:
            h = cls._content_hash(chunk.content)
            if h not in seen:
                seen.add(h)
                result.append(chunk)
        return result

    @staticmethod
    def _content_hash(text: str) -> str:
        normalized = " ".join(text.split()).lower()
        return hashlib.sha256(normalized.encode()).hexdigest()


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
