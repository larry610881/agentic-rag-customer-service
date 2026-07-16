"""BDD steps — DM 圖卡查詢去重與 context 組裝分離（POC 問題 7 regression）。"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.knowledge.value_objects import DocumentId
from src.domain.rag.value_objects import Source
from src.infrastructure.langgraph.dm_image_query_tool import DmImageQueryTool

scenarios("unit/agent/dm_image_query_dedup.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_doc(doc_id: str, page: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=DocumentId(value=doc_id),
        filename=f"page_{page:03d}.png",
        storage_path=f"tenant/dm/{doc_id}/page_{page:03d}.png",
        page_number=page,
        content_type="image/png",
    )


def _make_source(doc_id: str, score: float, snippet: str) -> Source:
    return Source(
        document_name="dm",
        content_snippet=snippet,
        score=score,
        chunk_id=f"chunk-{doc_id}-{int(score * 10000)}",
        document_id=doc_id,
    )


def _build_tool(retrieve_sources, docs) -> DmImageQueryTool:
    rag = AsyncMock()
    rag.retrieve = AsyncMock(
        return_value=SimpleNamespace(
            chunks=[s.content_snippet for s in retrieve_sources],
            sources=retrieve_sources,
        )
    )
    repo = AsyncMock()
    repo.find_by_ids = AsyncMock(return_value=docs)
    storage = AsyncMock()
    storage.get_preview_url = AsyncMock(
        side_effect=lambda path, expiry_seconds: f"https://signed/{path}"
    )
    return DmImageQueryTool(
        query_rag_use_case=rag,
        document_repository=repo,
        file_storage=storage,
    )


@pytest.fixture
def context():
    return {}


@given("DM 第 49 頁有幫寶適與包大人兩個商品且第 50 頁有寵物物語")
def setup_same_page_products(context):
    sources = [
        _make_source("doc-page49", 0.6375, "幫寶適 拉拉褲 二件省更多"),
        _make_source("doc-page49", 0.6337, "包大人 防漏安心復健褲 買1送1"),
        _make_source("doc-page50", 0.6179, "寵物物語尿布經濟包"),
    ]
    docs = [_make_doc("doc-page49", 49), _make_doc("doc-page50", 50)]
    context["tool"] = _build_tool(sources, docs)


@given("DM 知識庫查無相關商品")
def setup_no_hit(context):
    context["tool"] = _build_tool([], [])


@when("使用者查詢「包大人尿布有優惠嗎」", target_fixture="result")
def query_diapers(context):
    return _run(
        context["tool"].invoke(
            tenant_id="T1", kb_id="KB-DM", query="包大人尿布有優惠嗎"
        )
    )


@when("使用者查詢「不存在的商品」", target_fixture="result")
def query_missing(context):
    return _run(
        context["tool"].invoke(tenant_id="T1", kb_id="KB-DM", query="不存在的商品")
    )


@then("圖卡清單只包含 2 張（第 49 頁與第 50 頁各一）")
def verify_sources_deduped(result):
    assert len(result["sources"]) == 2
    assert sorted(s["page_number"] for s in result["sources"]) == [49, 50]


@then("context 文字同時包含「幫寶適」「包大人」「寵物物語」")
def verify_context_complete(result):
    for product in ("幫寶適", "包大人", "寵物物語"):
        assert product in result["context"]


@then("回傳空 context 與空圖卡清單")
def verify_empty(result):
    assert result == {"success": True, "context": "", "sources": []}
