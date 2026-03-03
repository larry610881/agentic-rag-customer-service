"""SQL Dump Text Splitter Service — main splitter for SQL dump files.

Orchestrates SqlSchemaParser, SqlDataExtractor, and ForeignKeyEnricher
to split SQL dumps into table-grouped chunks with FK enrichment.
"""

from __future__ import annotations

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.services import TextSplitterService
from src.domain.knowledge.value_objects import ChunkId
from src.infrastructure.text_splitter.sql_data_extractor import SqlDataExtractor
from src.infrastructure.text_splitter.sql_fk_enricher import ForeignKeyEnricher
from src.infrastructure.text_splitter.sql_schema_parser import SqlSchemaParser


class SqlDumpTextSplitterService(TextSplitterService):
    """Splits SQL dumps by table, enriching rows with FK references.

    Each chunk contains rows from a single table, prefixed with a table
    header showing the table name and column list.
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
        dialect = SqlSchemaParser.detect_dialect(text)
        schemas = SqlSchemaParser.parse_tables(text, dialect)
        table_data = SqlDataExtractor.extract(text, dialect, schemas)

        if not table_data:
            return []

        enricher = ForeignKeyEnricher(schemas, table_data)
        chunks: list[Chunk] = []

        for schema in schemas:
            rows = table_data.get(schema.name)
            if not rows:
                continue

            col_names = [c.name for c in schema.columns]
            header = f"[Table: {schema.name}]\nColumns: {', '.join(col_names)}\n---"
            header_len = len(header) + 1  # +1 for newline

            current_lines: list[str] = []
            current_size = header_len
            row_start = 0

            for row_idx, row in enumerate(rows):
                enriched_line = enricher.enrich_row(schema.name, row)
                line_len = len(enriched_line) + 1  # +1 for newline

                # Single row exceeds chunk_size → emit as standalone
                if header_len + line_len > self._chunk_size and not current_lines:
                    chunk_text = f"{header}\n{enriched_line}"
                    chunks.append(self._make_chunk(
                        chunk_text, document_id, tenant_id, content_type,
                        chunk_index=len(chunks),
                        table_name=schema.name,
                        row_start=row_idx,
                        row_end=row_idx,
                    ))
                    row_start = row_idx + 1
                    continue

                # Adding this row would exceed chunk_size → flush
                if current_size + line_len > self._chunk_size and current_lines:
                    chunk_text = header + "\n" + "\n".join(current_lines)
                    chunks.append(self._make_chunk(
                        chunk_text, document_id, tenant_id, content_type,
                        chunk_index=len(chunks),
                        table_name=schema.name,
                        row_start=row_start,
                        row_end=row_idx - 1,
                    ))
                    current_lines = []
                    current_size = header_len
                    row_start = row_idx

                current_lines.append(enriched_line)
                current_size += line_len

            # Flush remaining rows
            if current_lines:
                chunk_text = header + "\n" + "\n".join(current_lines)
                chunks.append(self._make_chunk(
                    chunk_text, document_id, tenant_id, content_type,
                    chunk_index=len(chunks),
                    table_name=schema.name,
                    row_start=row_start,
                    row_end=len(rows) - 1,
                ))

        return chunks

    @staticmethod
    def _make_chunk(
        content: str,
        document_id: str,
        tenant_id: str,
        content_type: str,
        chunk_index: int,
        table_name: str,
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
                "content_type": content_type or "application/sql",
                "table_name": table_name,
                "row_start": row_start,
                "row_end": row_end,
            },
        )
