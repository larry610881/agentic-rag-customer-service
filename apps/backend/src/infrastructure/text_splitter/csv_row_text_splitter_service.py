from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.services import TextSplitterService
from src.domain.knowledge.value_objects import ChunkId


class CSVRowTextSplitterService(TextSplitterService):
    """Row-based CSV splitter that preserves record integrity.

    Splits CSV text by rows, keeping each record intact.
    Each chunk is prefixed with the header row for context.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 0,
    ) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def split(
        self,
        text: str,
        document_id: str,
        tenant_id: str,
        content_type: str = "",
    ) -> list[Chunk]:
        lines = text.split("\n")
        # Remove trailing empty lines
        while lines and lines[-1].strip() == "":
            lines.pop()

        if not lines:
            return []

        # First line is header
        header = lines[0]
        data_rows = lines[1:]

        if not data_rows:
            return []

        header_len = len(header) + 1  # +1 for newline

        chunks: list[Chunk] = []
        current_rows: list[str] = []
        current_size = header_len

        for row in data_rows:
            if not row.strip():
                continue

            row_len = len(row) + 1  # +1 for newline

            # Single row exceeds chunk_size → emit as standalone chunk
            if header_len + row_len > self._chunk_size and not current_rows:
                chunk_text = f"{header}\n{row}"
                row_idx = len(chunks)
                chunks.append(
                    self._make_chunk(
                        chunk_text,
                        document_id,
                        tenant_id,
                        content_type,
                        chunk_index=row_idx,
                        row_start=self._data_row_index(data_rows, row, 0),
                        row_end=self._data_row_index(data_rows, row, 0),
                    )
                )
                continue

            # Adding this row would exceed chunk_size → flush current
            if current_size + row_len > self._chunk_size and current_rows:
                self._flush(
                    chunks,
                    header,
                    current_rows,
                    document_id,
                    tenant_id,
                    content_type,
                    data_rows,
                )
                current_rows = []
                current_size = header_len

            current_rows.append(row)
            current_size += row_len

        # Flush remaining rows
        if current_rows:
            self._flush(
                chunks,
                header,
                current_rows,
                document_id,
                tenant_id,
                content_type,
                data_rows,
            )

        return chunks

    def _flush(
        self,
        chunks: list[Chunk],
        header: str,
        rows: list[str],
        document_id: str,
        tenant_id: str,
        content_type: str,
        all_data_rows: list[str],
    ) -> None:
        chunk_text = header + "\n" + "\n".join(rows)
        first_row = rows[0]
        last_row = rows[-1]
        row_start = self._data_row_index(all_data_rows, first_row, 0)
        row_end = self._data_row_index(all_data_rows, last_row, row_start)
        chunks.append(
            self._make_chunk(
                chunk_text,
                document_id,
                tenant_id,
                content_type,
                chunk_index=len(chunks),
                row_start=row_start,
                row_end=row_end,
            )
        )

    @staticmethod
    def _data_row_index(
        data_rows: list[str], row: str, start: int
    ) -> int:
        for i in range(start, len(data_rows)):
            if data_rows[i] is row:
                return i
        return start

    @staticmethod
    def _make_chunk(
        content: str,
        document_id: str,
        tenant_id: str,
        content_type: str,
        chunk_index: int,
        row_start: int,
        row_end: int,
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
                "content_type": content_type or "text/csv",
                "row_start": row_start,
                "row_end": row_end,
            },
        )
