"""Chunk 去重 BDD Step Definitions"""

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.services import ChunkDeduplicationService
from src.domain.knowledge.value_objects import ChunkId

scenarios("unit/knowledge/chunk_deduplication.feature")


@pytest.fixture
def context():
    return {}


# --- Exact duplicate ---


@given("一組包含重複內容的 chunks")
def duplicate_chunks(context):
    context["chunks"] = [
        Chunk(
            id=ChunkId(value="dup-1"),
            content="This is the same content repeated exactly.",
            chunk_index=0,
        ),
        Chunk(
            id=ChunkId(value="dup-2"),
            content="This is the same content repeated exactly.",
            chunk_index=1,
        ),
        Chunk(
            id=ChunkId(value="unique-1"),
            content="This is unique content that differs from others.",
            chunk_index=2,
        ),
    ]


@when("執行 chunk 去重")
def do_dedup(context):
    context["result"] = ChunkDeduplicationService.deduplicate(context["chunks"])


@then("重複的 chunks 應被移除")
def verify_dedup(context):
    assert len(context["result"]) == 2
    ids = [c.id.value for c in context["result"]]
    assert "dup-1" in ids  # first occurrence kept
    assert "dup-2" not in ids


# --- Whitespace difference ---


@given("一組內容相同但空白不同的 chunks")
def whitespace_diff_chunks(context):
    context["chunks"] = [
        Chunk(
            id=ChunkId(value="ws-1"),
            content="Hello   world  test",
            chunk_index=0,
        ),
        Chunk(
            id=ChunkId(value="ws-2"),
            content="Hello world test",
            chunk_index=1,
        ),
    ]


@then("空白差異的 chunks 應被視為重複並移除")
def verify_whitespace_dedup(context):
    assert len(context["result"]) == 1


# --- All unique ---


@given("一組內容各不相同的 chunks")
def unique_chunks(context):
    context["chunks"] = [
        Chunk(
            id=ChunkId(value=f"u-{i}"),
            content=f"Unique content number {i} that is different.",
            chunk_index=i,
        )
        for i in range(3)
    ]


@then("所有 chunks 應被保留")
def verify_all_unique_kept(context):
    assert len(context["result"]) == 3
