"""Unit tests for source-tracking schema + filter expression changes.

Focused, infra-internal tests — no Milvus instance required. Keeps the BDD
integration suite aimed at API contract while pinning the low-level
contracts (filter DSL + schema fields) here.
"""

from __future__ import annotations

import pytest
from pymilvus import DataType

from src.infrastructure.milvus.milvus_vector_store import (
    _KNOWN_FIELDS,
    _build_filter_expr,
    _build_schema,
    _sanitize_filter_value,
)

# ---------------------------------------------------------------------------
# Filter expression — IN operator (multi-value list)
# ---------------------------------------------------------------------------


def test_filter_expr_scalar_remains_equality():
    """Existing string == "value" behavior must not regress."""
    expr = _build_filter_expr({"tenant_id": "T001"})
    assert expr == 'tenant_id == "T001"'


def test_filter_expr_list_uses_in_operator():
    expr = _build_filter_expr({"source_id": ["12345", "12346", "12347"]})
    assert expr == 'source_id in ["12345", "12346", "12347"]'


def test_filter_expr_combines_scalar_and_list():
    """source == "x" AND source_id IN [...] is the typical DELETE /by-source filter."""
    expr = _build_filter_expr(
        {"source": "audit_log", "source_id": ["a", "b"]}
    )
    assert expr == 'source == "audit_log" and source_id in ["a", "b"]'


def test_filter_expr_list_sanitizes_each_value():
    """Each list element must pass _sanitize_filter_value (injection guard)."""
    with pytest.raises(ValueError, match="Unsafe filter value"):
        _build_filter_expr({"source_id": ["legit", 'evil"; DROP']})


def test_sanitize_value_quotes_safe_chars():
    assert _sanitize_filter_value("audit_log") == '"audit_log"'
    assert _sanitize_filter_value("a-b.c:d/e_f") == '"a-b.c:d/e_f"'


# ---------------------------------------------------------------------------
# Schema — source / source_id are first-class fields
# ---------------------------------------------------------------------------


def test_known_fields_includes_source_and_source_id():
    """upsert() extracts these into first-class columns instead of `extra`."""
    assert "source" in _KNOWN_FIELDS
    assert "source_id" in _KNOWN_FIELDS


def test_schema_has_source_first_class_field():
    schema = _build_schema(vector_size=3072)
    field_names = {f.name for f in schema.fields}
    assert "source" in field_names
    assert "source_id" in field_names


def test_source_field_is_varchar_64_with_default():
    schema = _build_schema(vector_size=3072)
    src = next(f for f in schema.fields if f.name == "source")
    assert src.dtype == DataType.VARCHAR
    # max_length lives in field params under pymilvus 2.x
    assert src.params.get("max_length") == 64


def test_source_id_field_is_varchar_128():
    schema = _build_schema(vector_size=3072)
    src_id = next(f for f in schema.fields if f.name == "source_id")
    assert src_id.dtype == DataType.VARCHAR
    assert src_id.params.get("max_length") == 128


def test_schema_keeps_existing_first_class_fields():
    """Regression guard: do not silently drop existing fields when extending."""
    schema = _build_schema(vector_size=3072)
    field_names = {f.name for f in schema.fields}
    for required in (
        "id", "vector", "tenant_id", "document_id", "content",
        "chunk_index", "content_type", "language", "extra",
    ):
        assert required in field_names, (
            f"Existing field {required!r} was dropped when adding source/source_id"
        )
