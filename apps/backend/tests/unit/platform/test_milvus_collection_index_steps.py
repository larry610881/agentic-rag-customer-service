"""Milvus Vector Store Collection BDD Step Definitions"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("unit/platform/milvus_collection_index.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given("一個 Milvus Vector Store")
def setup_vector_store(context):
    from src.infrastructure.milvus.milvus_vector_store import MilvusVectorStore

    mock_client = MagicMock()
    mock_client.has_collection.return_value = False
    mock_client.create_collection.return_value = None
    mock_client.prepare_index_params.return_value = MagicMock()

    with patch(
        "src.infrastructure.milvus.milvus_vector_store.MilvusClient",
        return_value=mock_client,
    ):
        store = MilvusVectorStore(uri="http://localhost:19530")
    store._client = mock_client
    context["store"] = store
    context["mock_client"] = mock_client


@when("執行 ensure_collection")
def run_ensure_collection(context):
    _run(context["store"].ensure_collection("test_collection", 1536))


@then("應成功建立包含 tenant_id 和 document_id 欄位的 collection")
def verify_collection_created(context):
    mock_client = context["mock_client"]
    mock_client.create_collection.assert_called_once()

    call_kwargs = mock_client.create_collection.call_args
    schema = call_kwargs.kwargs.get("schema") or call_kwargs[1].get("schema")

    field_names = [f.name for f in schema.fields]
    assert "tenant_id" in field_names
    assert "document_id" in field_names
    assert "vector" in field_names
    assert "id" in field_names
