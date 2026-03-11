"""Qdrant Payload Index BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.qdrant.qdrant_vector_store import QdrantVectorStore

scenarios("unit/platform/qdrant_payload_index.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given("一個 Qdrant Vector Store")
def setup_vector_store(context):
    mock_client = AsyncMock()
    # Simulate collection does not exist yet
    collections_response = MagicMock()
    collections_response.collections = []
    mock_client.get_collections.return_value = collections_response
    mock_client.create_collection.return_value = None
    mock_client.create_payload_index.return_value = None

    store = QdrantVectorStore.__new__(QdrantVectorStore)
    store._client = mock_client
    context["store"] = store
    context["mock_client"] = mock_client


@when("執行 ensure_collection")
def run_ensure_collection(context):
    _run(context["store"].ensure_collection("test_collection", 1536))


@then("應建立 tenant_id 和 document_id 的 payload index")
def verify_payload_indexes(context):
    mock_client = context["mock_client"]
    index_calls = mock_client.create_payload_index.call_args_list
    assert len(index_calls) == 2

    # Verify tenant_id index
    _, kwargs0 = index_calls[0]
    assert kwargs0["collection_name"] == "test_collection"
    assert kwargs0["field_name"] == "tenant_id"
    assert kwargs0["field_schema"] == "keyword"

    # Verify document_id index
    _, kwargs1 = index_calls[1]
    assert kwargs1["collection_name"] == "test_collection"
    assert kwargs1["field_name"] == "document_id"
    assert kwargs1["field_schema"] == "keyword"
