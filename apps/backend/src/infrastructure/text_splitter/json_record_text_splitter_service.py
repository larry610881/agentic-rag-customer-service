import json

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.services import TextSplitterService
from src.domain.knowledge.value_objects import ChunkId


class JsonRecordTextSplitterService(TextSplitterService):
    """Record-based JSON splitter that preserves object integrity.

    Splits JSON arrays of objects by record boundaries, keeping each
    record intact. Multiple small records are grouped into one chunk
    up to ``chunk_size``. Falls back to a recursive splitter for
    non-array JSON.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        fallback: TextSplitterService | None = None,
    ) -> None:
        self._chunk_size = chunk_size
        self._fallback = fallback

    def split(
        self,
        text: str,
        document_id: str,
        tenant_id: str,
        content_type: str = "",
    ) -> list[Chunk]:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return self._do_fallback(text, document_id, tenant_id, content_type)

        records = self._extract_records(data)
        if records is None:
            return self._do_fallback(text, document_id, tenant_id, content_type)

        chunks: list[Chunk] = []
        buffer: list[str] = []
        buffer_size = 0
        record_start = 0

        for i, record in enumerate(records):
            record_text = self._format_record(record)
            record_len = len(record_text)

            # Single record exceeds chunk_size → emit as standalone chunk
            if not buffer and record_len > self._chunk_size:
                chunks.append(
                    self._make_chunk(
                        record_text,
                        document_id,
                        tenant_id,
                        content_type,
                        chunk_index=len(chunks),
                        record_start=i,
                        record_end=i,
                    )
                )
                record_start = i + 1
                continue

            # Adding this record would exceed chunk_size → flush
            if buffer and buffer_size + len("\n\n") + record_len > self._chunk_size:
                chunks.append(
                    self._make_chunk(
                        "\n\n".join(buffer),
                        document_id,
                        tenant_id,
                        content_type,
                        chunk_index=len(chunks),
                        record_start=record_start,
                        record_end=i - 1,
                    )
                )
                buffer = []
                buffer_size = 0
                record_start = i

            buffer.append(record_text)
            buffer_size += (len("\n\n") if buffer_size > 0 else 0) + record_len

        if buffer:
            chunks.append(
                self._make_chunk(
                    "\n\n".join(buffer),
                    document_id,
                    tenant_id,
                    content_type,
                    chunk_index=len(chunks),
                    record_start=record_start,
                    record_end=len(records) - 1,
                )
            )

        return chunks

    @staticmethod
    def _extract_records(data: object) -> list[dict] | None:
        """Extract a list of record dicts from parsed JSON."""
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    return v
        return None

    @staticmethod
    def _format_record(record: dict) -> str:
        """Format a single JSON object as readable key: value lines."""
        lines: list[str] = []
        for key, value in record.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _make_chunk(
        content: str,
        document_id: str,
        tenant_id: str,
        content_type: str,
        chunk_index: int,
        record_start: int,
        record_end: int,
    ) -> Chunk:
        return Chunk(
            id=ChunkId(),
            document_id=document_id,
            tenant_id=tenant_id,
            content=content,
            chunk_index=chunk_index,
            metadata={
                "document_id": document_id,
                "tenant_id": tenant_id,
                "content_type": content_type or "application/json",
                "record_start": record_start,
                "record_end": record_end,
            },
        )

    def _do_fallback(
        self,
        text: str,
        document_id: str,
        tenant_id: str,
        content_type: str,
    ) -> list[Chunk]:
        if self._fallback:
            return self._fallback.split(text, document_id, tenant_id, content_type)
        return []
