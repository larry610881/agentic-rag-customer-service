"""SQL Data Extractor — DML parsing for INSERT / COPY statements.

Extracts row data from MySQL INSERT INTO and PostgreSQL COPY FROM stdin
statements. Returns a dict mapping table names to lists of row dicts.
"""

from __future__ import annotations

import re

from src.infrastructure.text_splitter.sql_schema_parser import (
    SqlDialect,
    TableSchema,
)

# ---------------------------------------------------------------------------
# INSERT parsing (MySQL)
# ---------------------------------------------------------------------------
# Header-only regex: captures table name & optional column list up to VALUES.
# Value tuples are parsed by a stateful parser to handle ')' inside strings.
_INSERT_HEADER_RE = re.compile(
    r"INSERT\s+INTO\s+(?:[`\"]*\w+[`\"]*\.)?[`\"]*(\w+)[`\"]*"
    r"\s*(?:\(([^)]+)\)\s*)?VALUES\s*",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# COPY parsing (PostgreSQL)
# ---------------------------------------------------------------------------
_COPY_HEADER_RE = re.compile(
    r"COPY\s+(?:[\"]*\w+[\"]*\.)?[\"]*(\w+)[\"]*\s*\(([^)]+)\)\s*FROM\s+stdin\s*;",
    re.IGNORECASE,
)


class SqlDataExtractor:
    """Stateless extractor for SQL dump DML."""

    @classmethod
    def extract(
        cls,
        text: str,
        dialect: SqlDialect,
        schemas: list[TableSchema],
    ) -> dict[str, list[dict[str, str]]]:
        if dialect == SqlDialect.MYSQL:
            return cls._extract_mysql(text, schemas)
        return cls._extract_pg(text, schemas)

    @classmethod
    def _extract_mysql(
        cls,
        text: str,
        schemas: list[TableSchema],
    ) -> dict[str, list[dict[str, str]]]:
        # Build schema lookup for fallback column names
        schema_map = {s.name: s for s in schemas}

        result: dict[str, list[dict[str, str]]] = {}
        for match in _INSERT_HEADER_RE.finditer(text):
            table = match.group(1)
            col_group = match.group(2)
            if col_group:
                col_names = [c.strip().strip("`\"") for c in col_group.split(",")]
            elif table in schema_map:
                col_names = [c.name for c in schema_map[table].columns]
            else:
                continue

            values_str = cls._extract_values_body(text, match.end())
            if not values_str:
                continue
            rows = cls._parse_insert_values(values_str, col_names)
            result.setdefault(table, []).extend(rows)
        return result

    @staticmethod
    def _extract_values_body(text: str, start: int) -> str:
        """Extract everything from start up to the terminating ';'.

        Respects quoted strings so a ';' inside a string is not mistaken
        for the statement terminator.
        """
        i = start
        in_quote = False
        quote_char = ""
        while i < len(text):
            ch = text[i]
            if in_quote:
                if ch == "\\" and i + 1 < len(text):
                    i += 2
                    continue
                if ch == quote_char:
                    if i + 1 < len(text) and text[i + 1] == quote_char:
                        i += 2
                        continue
                    in_quote = False
            else:
                if ch in ("'", '"'):
                    in_quote = True
                    quote_char = ch
                elif ch == ";":
                    return text[start:i]
            i += 1
        return text[start:]

    @classmethod
    def _parse_insert_values(
        cls, values_str: str, col_names: list[str]
    ) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        tuples = cls._split_value_tuples(values_str)
        for tup in tuples:
            values = cls._parse_single_tuple(tup)
            row = {}
            for i, val in enumerate(values):
                if i < len(col_names):
                    row[col_names[i]] = val
            rows.append(row)
        return rows

    @staticmethod
    def _split_value_tuples(values_str: str) -> list[str]:
        """Split (v1,v2),(v3,v4) into individual tuple strings.

        Quote-aware: parentheses inside single/double-quoted strings
        (e.g. ``'size (L)'``) are ignored for depth tracking.
        """
        tuples: list[str] = []
        depth = 0
        current: list[str] = []
        in_quote = False
        quote_char = ""
        i = 0
        while i < len(values_str):
            ch = values_str[i]
            if in_quote:
                if ch == "\\" and i + 1 < len(values_str):
                    # Backslash escape — consume next char verbatim
                    if depth > 0:
                        current.append(ch)
                        current.append(values_str[i + 1])
                    i += 2
                    continue
                if ch == quote_char:
                    # Doubled-quote escape (e.g. '')
                    if i + 1 < len(values_str) and values_str[i + 1] == quote_char:
                        if depth > 0:
                            current.append(ch)
                            current.append(values_str[i + 1])
                        i += 2
                        continue
                    in_quote = False
                if depth > 0:
                    current.append(ch)
            else:
                if ch in ("'", '"'):
                    in_quote = True
                    quote_char = ch
                    if depth > 0:
                        current.append(ch)
                elif ch == "(":
                    if depth == 0:
                        current = []
                    else:
                        current.append(ch)
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        tuples.append("".join(current))
                    else:
                        current.append(ch)
                else:
                    if depth > 0:
                        current.append(ch)
            i += 1
        return tuples

    @staticmethod
    def _parse_single_tuple(tup: str) -> list[str]:
        """Parse a single value tuple like: 1,'Alice','hello, world'"""
        values: list[str] = []
        current: list[str] = []
        in_quote = False
        quote_char = ""
        i = 0
        while i < len(tup):
            ch = tup[i]
            if in_quote:
                if ch == "\\" and i + 1 < len(tup):
                    current.append(tup[i + 1])
                    i += 2
                    continue
                if ch == quote_char:
                    # Check for escaped quote ('')
                    if i + 1 < len(tup) and tup[i + 1] == quote_char:
                        current.append(ch)
                        i += 2
                        continue
                    in_quote = False
                else:
                    current.append(ch)
            else:
                if ch in ("'", '"'):
                    in_quote = True
                    quote_char = ch
                elif ch == ",":
                    values.append("".join(current).strip())
                    current = []
                else:
                    current.append(ch)
            i += 1
        values.append("".join(current).strip())
        return values

    @classmethod
    def _extract_pg(
        cls,
        text: str,
        schemas: list[TableSchema],
    ) -> dict[str, list[dict[str, str]]]:
        result: dict[str, list[dict[str, str]]] = {}
        for match in _COPY_HEADER_RE.finditer(text):
            table = match.group(1)
            col_names = [c.strip().strip('"') for c in match.group(2).split(",")]
            # Find data lines after the COPY header until \.
            start_pos = match.end()
            lines = text[start_pos:].split("\n")
            rows: list[dict[str, str]] = []
            for line in lines:
                stripped = line.strip()
                if stripped == "\\.":
                    break
                if not stripped:
                    continue
                values = stripped.split("\t")
                row = {}
                for i, val in enumerate(values):
                    if i < len(col_names):
                        col = col_names[i]
                        row[col] = val if val != "\\N" else ""
                rows.append(row)
            result.setdefault(table, []).extend(rows)
        return result
