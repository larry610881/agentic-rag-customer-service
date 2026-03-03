"""SQL Schema Parser — dialect detection + DDL parsing.

Parses CREATE TABLE statements to extract schema, columns, primary keys,
and foreign key relationships. Supports MySQL and PostgreSQL dump formats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class SqlDialect(str, Enum):
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"


@dataclass(frozen=True)
class ColumnDef:
    name: str
    data_type: str


@dataclass(frozen=True)
class ForeignKeyDef:
    source_table: str
    source_columns: tuple[str, ...]
    target_table: str
    target_columns: tuple[str, ...]


@dataclass
class TableSchema:
    name: str
    columns: list[ColumnDef] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKeyDef] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dialect detection patterns
# ---------------------------------------------------------------------------
_MYSQL_INDICATORS = re.compile(
    r"`[^`]+`|ENGINE\s*=|AUTO_INCREMENT|UNSIGNED|COMMENT\s+'",
    re.IGNORECASE,
)
_PG_INDICATORS = re.compile(
    r"COPY\s+\S+\s+FROM\s+stdin|(?:big)?serial|::\w+|NOW\(\)|OWNER\s+TO",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# DDL parsing patterns
# ---------------------------------------------------------------------------
_CREATE_TABLE_HEADER_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]*(\w+)[`\"]*\s*\(",
    re.IGNORECASE,
)

_STRIP_QUOTES = re.compile(r"[`\"\[\]]")

_PK_CONSTRAINT_RE = re.compile(
    r"PRIMARY\s+KEY\s*\(([^)]+)\)", re.IGNORECASE
)
_FK_CONSTRAINT_RE = re.compile(
    r"FOREIGN\s+KEY\s*\(([^)]+)\)\s*REFERENCES\s+[`\"]*(\w+)[`\"]*\s*\(([^)]+)\)",
    re.IGNORECASE,
)


class SqlSchemaParser:
    """Stateless parser for SQL dump DDL."""

    @staticmethod
    def detect_dialect(text: str) -> SqlDialect:
        mysql_score = len(_MYSQL_INDICATORS.findall(text))
        pg_score = len(_PG_INDICATORS.findall(text))
        return SqlDialect.POSTGRESQL if pg_score > mysql_score else SqlDialect.MYSQL

    @classmethod
    def parse_tables(cls, text: str, dialect: SqlDialect) -> list[TableSchema]:
        tables: list[TableSchema] = []
        for match in _CREATE_TABLE_HEADER_RE.finditer(text):
            table_name = _STRIP_QUOTES.sub("", match.group(1))
            body = cls._extract_paren_body(text, match.end() - 1)
            if body is not None:
                schema = cls._parse_create_body(table_name, body)
                tables.append(schema)
        return tables

    @staticmethod
    def _extract_paren_body(text: str, open_pos: int) -> str | None:
        """Extract content between matching parentheses at open_pos."""
        if open_pos >= len(text) or text[open_pos] != "(":
            return None
        depth = 0
        start = open_pos + 1
        for i in range(open_pos, len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    return text[start:i]
        return None

    @classmethod
    def _parse_create_body(cls, table_name: str, body: str) -> TableSchema:
        columns: list[ColumnDef] = []
        primary_key: list[str] = []
        foreign_keys: list[ForeignKeyDef] = []

        # Extract PK constraints
        for pk_match in _PK_CONSTRAINT_RE.finditer(body):
            pk_cols = cls._split_col_list(pk_match.group(1))
            primary_key.extend(pk_cols)

        # Extract FK constraints
        for fk_match in _FK_CONSTRAINT_RE.finditer(body):
            src_cols = tuple(cls._split_col_list(fk_match.group(1)))
            tgt_table = _STRIP_QUOTES.sub("", fk_match.group(2))
            tgt_cols = tuple(cls._split_col_list(fk_match.group(3)))
            foreign_keys.append(ForeignKeyDef(
                source_table=table_name,
                source_columns=src_cols,
                target_table=tgt_table,
                target_columns=tgt_cols,
            ))

        # Parse column definitions (lines that aren't constraints)
        for line in cls._split_body_lines(body):
            line_stripped = line.strip().rstrip(",")
            upper = line_stripped.upper()
            if any(kw in upper for kw in (
                "PRIMARY KEY", "FOREIGN KEY", "UNIQUE KEY",
                "KEY ", "INDEX ", "CONSTRAINT",
            )):
                continue
            col = cls._parse_column_line(line_stripped)
            if col:
                columns.append(col)

        return TableSchema(
            name=table_name,
            columns=columns,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
        )

    @staticmethod
    def _parse_column_line(line: str) -> ColumnDef | None:
        line = line.strip().rstrip(",")
        if not line:
            return None
        parts = line.split()
        if len(parts) < 2:
            return None
        name = _STRIP_QUOTES.sub("", parts[0])
        data_type = parts[1].upper().rstrip(",")
        return ColumnDef(name=name, data_type=data_type)

    @staticmethod
    def _split_col_list(col_str: str) -> list[str]:
        return [_STRIP_QUOTES.sub("", c.strip()) for c in col_str.split(",")]

    @staticmethod
    def _split_body_lines(body: str) -> list[str]:
        """Split CREATE TABLE body into logical lines, respecting parentheses."""
        lines: list[str] = []
        current: list[str] = []
        depth = 0
        for char in body:
            if char == "(":
                depth += 1
                current.append(char)
            elif char == ")":
                depth -= 1
                current.append(char)
            elif char == "," and depth == 0:
                lines.append("".join(current))
                current = []
            else:
                current.append(char)
        if current:
            lines.append("".join(current))
        return lines
