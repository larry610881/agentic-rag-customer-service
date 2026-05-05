"""DmImageQueryTool unit tests — 驗證去重、排序、cap、缺 storage_path filter。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.knowledge.value_objects import DocumentId
from src.domain.rag.value_objects import Source
from src.infrastructure.langgraph.dm_image_query_tool import DmImageQueryTool


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_doc(
    doc_id: str,
    page: int,
    storage_path: str | None = None,
    content_type: str = "image/png",
):
    if storage_path is None:
        storage_path = f"tenant/doc/{doc_id}/page_{page:03d}.png"
    return SimpleNamespace(
        id=DocumentId(value=doc_id),
        filename=f"page_{page:03d}.png",
        storage_path=storage_path,
        page_number=page,
        content_type=content_type,
    )


def _make_source(doc_id: str, score: float, snippet: str = "snippet"):
    return Source(
        document_name="x",
        content_snippet=snippet,
        score=score,
        chunk_id=f"chunk-{doc_id}-{int(score * 100)}",
        document_id=doc_id,
    )


def _build_tool(retrieve_sources, docs, *, max_images=12):
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

    async def signed(path, expiry_seconds):
        return f"https://signed/{path}?ttl={expiry_seconds}"

    storage.get_preview_url = AsyncMock(side_effect=signed)
    return DmImageQueryTool(
        query_rag_use_case=rag,
        document_repository=repo,
        file_storage=storage,
        signed_url_ttl_seconds=3600,
        max_images=max_images,
    )


@pytest.fixture
def common_kwargs():
    return {
        "tenant_id": "T1",
        "kb_id": "KB1",
        "query": "衛生紙促銷",
        "top_k": 5,
        "score_threshold": 0.3,
    }


def test_no_hit_returns_empty(common_kwargs):
    tool = _build_tool([], [])
    result = _run(tool.invoke(**common_kwargs))
    assert result == {"success": True, "context": "", "sources": []}


def test_dedup_same_document_keeps_highest_score(common_kwargs):
    sources = [
        _make_source("doc-21", 0.6, "page21 chunk1"),
        _make_source("doc-21", 0.9, "page21 chunk2 best"),
        _make_source("doc-21", 0.5, "page21 chunk3"),
    ]
    docs = [_make_doc("doc-21", 21)]
    tool = _build_tool(sources, docs)
    result = _run(tool.invoke(**common_kwargs))
    assert len(result["sources"]) == 1
    assert result["sources"][0]["page_number"] == 21
    assert "best" in result["sources"][0]["content_snippet"]
    assert result["sources"][0]["score"] == 0.9


def test_multi_pages_sorted_by_score_desc(common_kwargs):
    sources = [
        _make_source("doc-17", 0.5, "p17"),
        _make_source("doc-21", 0.9, "p21"),
        _make_source("doc-19", 0.7, "p19"),
    ]
    docs = [_make_doc("doc-17", 17), _make_doc("doc-21", 21), _make_doc("doc-19", 19)]
    tool = _build_tool(sources, docs)
    result = _run(tool.invoke(**common_kwargs))
    pages = [s["page_number"] for s in result["sources"]]
    assert pages == [21, 19, 17]


def test_cap_max_images(common_kwargs):
    # 15 unique docs，scores 不同
    sources = [
        _make_source(f"doc-{i}", 0.9 - (i * 0.01), f"p{i}") for i in range(15)
    ]
    docs = [_make_doc(f"doc-{i}", i) for i in range(15)]
    tool = _build_tool(sources, docs, max_images=12)
    result = _run(tool.invoke(**common_kwargs))
    assert len(result["sources"]) == 12
    # 取 score top 12 → 對應 page 0..11
    pages = [s["page_number"] for s in result["sources"]]
    assert pages == list(range(12))


def test_filter_doc_without_storage_path(common_kwargs):
    sources = [
        _make_source("doc-21", 0.9, "p21"),
        _make_source("doc-22", 0.8, "p22"),
    ]
    docs = [
        _make_doc("doc-21", 21),
        _make_doc("doc-22", 22, storage_path=""),  # 沒 storage_path
    ]
    tool = _build_tool(sources, docs)
    result = _run(tool.invoke(**common_kwargs))
    assert len(result["sources"]) == 1
    assert result["sources"][0]["page_number"] == 21


def test_filter_non_image_content_type(common_kwargs):
    """FAQ KB 的 JSON 等非 image doc 即使被搜到也不該推進 Flex carousel。"""
    sources = [
        _make_source("dm-21", 0.9, "p21"),
        _make_source("faq-1", 0.95, "faq json hit"),
    ]
    docs = [
        _make_doc("dm-21", 21),  # default content_type=image/png
        _make_doc("faq-1", 0, content_type="application/json"),
    ]
    tool = _build_tool(sources, docs)
    result = _run(tool.invoke(**common_kwargs))
    # JSON 過濾掉，只剩 dm-21
    assert len(result["sources"]) == 1
    assert result["sources"][0]["document_id"] == "dm-21"


def test_dedup_same_storage_path_across_different_documents(common_kwargs):
    """Regression: 不同 document_id 但同一個 storage_path（同一張 PNG，
    通常源於同一份 DM 被處理 / 上傳兩次）應該 dedup 成 1 筆，不能在
    LINE / Web / Widget carousel 連續顯示兩張同頁圖。

    Dedup 在 source 層做 — 所有通路自動一致，不需各自 channel handler 處理。
    """
    sources = [
        _make_source("doc-page54-a", 0.8, "page 54 chunk A"),
        _make_source("doc-page54-b", 0.95, "page 54 chunk B (best)"),
        _make_source("doc-page17", 0.7, "p17"),
    ]
    docs = [
        # 兩個 doc 不同 id 但指向同一張實體 PNG
        _make_doc("doc-page54-a", 54, storage_path="tenant/dm/page_054.png"),
        _make_doc("doc-page54-b", 54, storage_path="tenant/dm/page_054.png"),
        _make_doc("doc-page17", 17),
    ]
    tool = _build_tool(sources, docs)
    result = _run(tool.invoke(**common_kwargs))

    # 應只回 2 筆（page 54 + page 17），同 storage_path 已合併
    assert len(result["sources"]) == 2
    page_numbers = [s["page_number"] for s in result["sources"]]
    assert sorted(page_numbers) == [17, 54]

    # 同 storage_path 留下高分那筆（doc-page54-b score=0.95）
    page54 = next(s for s in result["sources"] if s["page_number"] == 54)
    assert page54["score"] == 0.95
    assert "best" in page54["content_snippet"]


def test_dedup_same_page_number_different_storage_paths(common_kwargs):
    """Regression（carrefour 真實案例）：同份 DM 重新上傳生出兩棵 child tree，
    各自 storage_path 不同（路徑各自包 document_id），但 page_number 相同。
    storage_path dedup 抓不到，必須再用 page_number 補一刀。

    範例：
    - 父 A 已被刪（orphan），剩 child page_054 storage_path=tenant/A/.../page_054.png
    - 父 B 還在，child page_054 storage_path=tenant/B/.../page_054.png
    兩個 child 的 page_number 都是 54 → carousel 會看到兩張一樣的 page 54。
    """
    sources = [
        _make_source("doc-orphan-54", 0.7, "page 54 chunk from orphan tree"),
        _make_source("doc-current-54", 0.92, "page 54 chunk from current tree (best)"),
        _make_source("doc-page21", 0.6, "p21"),
    ]
    docs = [
        # 兩個 doc 都是 page 54，但 storage_path 不同（包各自 document_id）
        _make_doc(
            "doc-orphan-54", 54,
            storage_path="tenant/orphan-tree-id/doc-orphan-54/page_054.png",
        ),
        _make_doc(
            "doc-current-54", 54,
            storage_path="tenant/current-tree-id/doc-current-54/page_054.png",
        ),
        _make_doc("doc-page21", 21),
    ]
    tool = _build_tool(sources, docs)
    result = _run(tool.invoke(**common_kwargs))

    # page 54 應只有 1 筆（即使 storage_path 不同），加上 page 21 共 2 筆
    assert len(result["sources"]) == 2
    page_numbers = sorted(s["page_number"] for s in result["sources"])
    assert page_numbers == [21, 54]

    # 留下分數高的那筆（doc-current-54 score=0.92）
    page54 = next(s for s in result["sources"] if s["page_number"] == 54)
    assert page54["score"] == 0.92
    assert "best" in page54["content_snippet"]


def test_no_dedup_when_page_number_zero(common_kwargs):
    """page_number == 0（非分頁文件，例如單張圖片）不該被 page dedup 合併。"""
    sources = [
        _make_source("img-a", 0.9, "image A"),
        _make_source("img-b", 0.8, "image B"),
    ]
    docs = [
        _make_doc("img-a", 0, storage_path="tenant/imgs/a.png"),
        _make_doc("img-b", 0, storage_path="tenant/imgs/b.png"),
    ]
    tool = _build_tool(sources, docs)
    result = _run(tool.invoke(**common_kwargs))
    # 兩張不同的單頁圖都應保留
    assert len(result["sources"]) == 2


def test_passes_kb_ids_to_rag_when_provided():
    """multi-KB scenario: invoke 帶 kb_ids → query_rag 收到 kb_ids list。"""
    rag = AsyncMock()
    rag.retrieve = AsyncMock(
        return_value=SimpleNamespace(chunks=[], sources=[]),
    )
    repo = AsyncMock()
    repo.find_by_ids = AsyncMock(return_value=[])
    storage = AsyncMock()
    from src.infrastructure.langgraph.dm_image_query_tool import (
        DmImageQueryTool,
    )

    tool = DmImageQueryTool(
        query_rag_use_case=rag,
        document_repository=repo,
        file_storage=storage,
    )
    _run(
        tool.invoke(
            tenant_id="T1",
            kb_id="KB1",
            kb_ids=["KB1", "KB2"],
            query="衛生紙",
        ),
    )
    # 確認 retrieve 收到的 command 含 kb_ids
    call_args = rag.retrieve.call_args
    cmd = call_args.args[0] if call_args.args else call_args.kwargs.get("command")
    assert cmd.kb_ids == ["KB1", "KB2"]
    assert cmd.kb_id == "KB1"  # backward compat single ID 仍傳
