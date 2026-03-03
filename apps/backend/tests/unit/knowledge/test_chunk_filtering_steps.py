"""Chunk 過濾 BDD Step Definitions"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.services import ChunkFilterService
from src.domain.knowledge.value_objects import ChunkId

scenarios("unit/knowledge/chunk_filtering.feature")


@pytest.fixture
def context():
    return {}


# --- Too short ---


@given("一組包含過短內容的 chunks")
def short_chunks(context):
    context["chunks"] = [
        Chunk(id=ChunkId(value="short-1"), content="Hi", chunk_index=0),
        Chunk(
            id=ChunkId(value="ok-1"),
            content="This is a sufficiently long chunk content for testing.",
            chunk_index=1,
        ),
    ]


@when("執行 chunk 過濾")
def do_filter(context):
    context["result"] = ChunkFilterService.filter(context["chunks"])


@then("過短的 chunks 應被拒絕")
def verify_short_rejected(context):
    accepted_ids = {c.id.value for c in context["result"].accepted}
    assert "short-1" not in accepted_ids
    assert context["result"].rejected_count >= 1


@then(parsers.parse('拒絕原因應為 "{reason}"'))
def verify_rejection_reason(context, reason):
    assert reason in context["result"].rejection_reasons.values()


# --- Noise only ---


@given("一組包含純符號內容的 chunks")
def noise_chunks(context):
    context["chunks"] = [
        Chunk(
            id=ChunkId(value="noise-1"),
            content="!!!  ### $$$ 123 456 ???",
            chunk_index=0,
        ),
        Chunk(
            id=ChunkId(value="ok-2"),
            content="This is a normal chunk with real content here.",
            chunk_index=1,
        ),
    ]


@then("純符號的 chunks 應被拒絕")
def verify_noise_rejected(context):
    accepted_ids = {c.id.value for c in context["result"].accepted}
    assert "noise-1" not in accepted_ids


# --- Normal chunks ---


@given("一組正常品質的 chunks 待過濾")
def normal_chunks(context):
    context["chunks"] = [
        Chunk(
            id=ChunkId(value=f"normal-{i}"),
            content=f"This is a normal quality chunk number {i} with enough content.",
            chunk_index=i,
        )
        for i in range(3)
    ]


@then("所有 chunks 應被保留")
def verify_all_kept(context):
    assert len(context["result"].accepted) == len(context["chunks"])
    assert context["result"].rejected_count == 0


# --- All filtered ---


@given("一組全部為低品質的 chunks")
def all_bad_chunks(context):
    context["chunks"] = [
        Chunk(id=ChunkId(value="bad-1"), content="x", chunk_index=0),
        Chunk(id=ChunkId(value="bad-2"), content="ab", chunk_index=1),
    ]


@then("應回傳空的 accepted 列表")
def verify_empty_accepted(context):
    assert len(context["result"].accepted) == 0
    assert context["result"].rejected_count == 2
