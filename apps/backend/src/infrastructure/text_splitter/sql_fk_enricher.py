"""SQL FK Enricher — enrich rows with foreign key referenced data.

For each row containing a FK column, looks up the referenced row in the
target table and appends descriptive (non-noise) fields to the row text.
Only performs one-hop lookups to avoid chunk bloat.
"""

from __future__ import annotations

from src.infrastructure.text_splitter.sql_schema_parser import TableSchema

# Column name suffixes/patterns considered noise (excluded from enrichment)
_NOISE_SUFFIXES = ("_id", "_at", "_url", "_uri")
_NOISE_EXACT = frozenset({"id", "created_at", "updated_at", "deleted_at"})


class ForeignKeyEnricher:
    """Enriches row data by resolving foreign key references."""

    def __init__(
        self,
        schemas: list[TableSchema],
        table_data: dict[str, list[dict[str, str]]],
    ) -> None:
        self._schemas = {s.name: s for s in schemas}
        self._table_data = table_data
        self._pk_lookups: dict[str, dict[str, dict[str, str]]] = {}
        self._build_pk_lookups()

    def _build_pk_lookups(self) -> None:
        """Build PK → row_dict lookup for each table that has a PK."""
        for schema in self._schemas.values():
            if not schema.primary_key:
                continue
            rows = self._table_data.get(schema.name, [])
            lookup: dict[str, dict[str, str]] = {}
            for row in rows:
                pk_values = tuple(
                    row.get(pk_col, "") for pk_col in schema.primary_key
                )
                pk_key = "|".join(pk_values)
                lookup[pk_key] = row
            self._pk_lookups[schema.name] = lookup

    def enrich_row(
        self, table_name: str, row: dict[str, str]
    ) -> str:
        """Format a row as text with FK enrichment appended."""
        base = self._format_row(table_name, row)
        schema = self._schemas.get(table_name)
        if not schema or not schema.foreign_keys:
            return base

        enrichments: list[str] = []
        for fk in schema.foreign_keys:
            fk_values = tuple(row.get(col, "") for col in fk.source_columns)
            if not any(fk_values):
                continue

            target_lookup = self._pk_lookups.get(fk.target_table)
            if not target_lookup:
                continue

            pk_key = "|".join(fk_values)
            target_row = target_lookup.get(pk_key)
            if not target_row:
                continue

            desc_fields = self._get_descriptive_fields(target_row)
            if desc_fields:
                parts = ", ".join(f"{k}={v}" for k, v in desc_fields.items())
                enrichments.append(f"[{fk.target_table}: {parts}]")

        if enrichments:
            return f"{base} {' '.join(enrichments)}"
        return base

    @staticmethod
    def _format_row(table_name: str, row: dict[str, str]) -> str:
        parts = ", ".join(f"{k}={v}" for k, v in row.items())
        return f"{table_name}: {parts}"

    @staticmethod
    def _get_descriptive_fields(row: dict[str, str]) -> dict[str, str]:
        """Filter out noise columns, keeping only descriptive fields."""
        result: dict[str, str] = {}
        for key, value in row.items():
            key_lower = key.lower()
            if key_lower in _NOISE_EXACT:
                continue
            if any(key_lower.endswith(s) for s in _NOISE_SUFFIXES):
                continue
            result[key] = value
        return result
