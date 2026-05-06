"""Layer 2 — MilvusVectorStore tenacity retry behavior."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from pymilvus.exceptions import (
    ConnectError,
    MilvusException,
    MilvusUnavailableException,
    ParamError,
)

from src.infrastructure.milvus.milvus_vector_store import (
    MilvusVectorStore,
    _is_milvus_retryable_error,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip retry waits to keep tests fast."""
    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant)


def _build_store_with_fake_client(client_methods: dict) -> MilvusVectorStore:
    store = MilvusVectorStore.__new__(MilvusVectorStore)
    store._client = MagicMock()
    store._schema_field_cache = {}
    for name, fn in client_methods.items():
        setattr(store._client, name, fn)
    return store


# ── predicate logic ─────────────────────────────────────────────


def test_predicate_retries_connect_error():
    assert _is_milvus_retryable_error(ConnectError(message="connection failed"))


def test_predicate_retries_milvus_unavailable():
    assert _is_milvus_retryable_error(
        MilvusUnavailableException(message="server unavailable")
    )


def test_predicate_retries_milvus_msg_with_connect_keyword():
    exc = MilvusException(message="Fail connecting to server on 127.0.0.1:19530")
    assert _is_milvus_retryable_error(exc)


def test_predicate_does_not_retry_param_error():
    """ParamError 是業務參數錯誤 — retry 不會自己變對。"""
    assert not _is_milvus_retryable_error(ParamError(message="invalid param"))


def test_predicate_does_not_retry_non_milvus():
    assert not _is_milvus_retryable_error(ValueError("bad"))


# ── upsert: connection blip → retry succeeds ────────────────────


def test_upsert_retries_on_transient_connect_error_then_succeeds():
    call_count = {"upsert": 0, "describe": 0}

    def fake_describe_collection(collection_name: str):
        call_count["describe"] += 1
        return {
            "fields": [
                {"name": "id"}, {"name": "vector"}, {"name": "tenant_id"},
                {"name": "document_id"}, {"name": "content"},
                {"name": "chunk_index"}, {"name": "content_type"},
                {"name": "language"}, {"name": "extra"},
            ]
        }

    def fake_upsert(collection_name: str, data: list):
        call_count["upsert"] += 1
        if call_count["upsert"] == 1:
            raise ConnectError(message="Fail connecting to server")
        return {"upsert_count": len(data)}

    store = _build_store_with_fake_client({
        "upsert": fake_upsert,
        "describe_collection": fake_describe_collection,
    })

    _run(store.upsert(
        collection="kb_test",
        ids=["c1"],
        vectors=[[0.1, 0.2]],
        payloads=[{"tenant_id": "T001", "content": "x"}],
    ))

    assert call_count["upsert"] == 2, "should retry once after transient fail"


def test_upsert_raises_after_max_retries():
    call_count = {"upsert": 0}

    def fake_describe_collection(collection_name: str):
        return {"fields": []}  # empty → store falls back to passing all keys

    def fake_upsert(collection_name: str, data: list):
        call_count["upsert"] += 1
        raise ConnectError(message="Fail connecting to server")

    store = _build_store_with_fake_client({
        "upsert": fake_upsert,
        "describe_collection": fake_describe_collection,
    })

    with pytest.raises(ConnectError):
        _run(store.upsert(
            collection="kb_test",
            ids=["c1"],
            vectors=[[0.1, 0.2]],
            payloads=[{"tenant_id": "T001", "content": "x"}],
        ))

    assert call_count["upsert"] == 3, "should attempt exactly MAX_TRIES=3"


def test_upsert_does_not_retry_param_error():
    """ParamError = 業務錯誤，retry 浪費。第一次直接 raise。"""
    call_count = {"upsert": 0}

    def fake_describe_collection(collection_name: str):
        return {"fields": []}

    def fake_upsert(collection_name: str, data: list):
        call_count["upsert"] += 1
        raise ParamError(message="invalid filter")

    store = _build_store_with_fake_client({
        "upsert": fake_upsert,
        "describe_collection": fake_describe_collection,
    })

    with pytest.raises(ParamError):
        _run(store.upsert(
            collection="kb_test",
            ids=["c1"],
            vectors=[[0.1, 0.2]],
            payloads=[{}],
        ))

    assert call_count["upsert"] == 1, "ParamError must not trigger retry"


# ── search: same retry semantics ────────────────────────────────


def test_search_retries_on_milvus_unavailable():
    call_count = {"search": 0, "describe": 0}

    def fake_describe(collection_name: str):
        call_count["describe"] += 1
        return {"fields": []}

    def fake_search(**_kwargs):
        call_count["search"] += 1
        if call_count["search"] < 2:
            raise MilvusUnavailableException(message="server unavailable")
        return [[]]  # empty results, valid shape

    store = _build_store_with_fake_client({
        "search": fake_search,
        "describe_collection": fake_describe,
    })

    results = _run(store.search(
        collection="kb_test",
        query_vector=[0.1, 0.2],
        limit=5,
    ))

    assert call_count["search"] == 2
    assert results == []


# ── drop_collection: retries and re-raises (handler relies on raise) ──


def test_drop_collection_retries_on_connect_error_then_succeeds():
    call_count = {"has": 0, "drop": 0}

    def fake_has(collection_name: str):
        call_count["has"] += 1
        return True

    def fake_drop(collection_name: str):
        call_count["drop"] += 1
        if call_count["drop"] < 2:
            raise ConnectError(message="Fail connecting to server")
        return None

    store = _build_store_with_fake_client({
        "has_collection": fake_has,
        "drop_collection": fake_drop,
    })

    _run(store.drop_collection("kb_test"))
    assert call_count["drop"] == 2
