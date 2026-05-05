"""驗證 ReActAgentService._build_builtin_tools 正確套用 per-tool RAG 參數。"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.langgraph.react_agent_service import ReActAgentService


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def service() -> ReActAgentService:
    """Build a ReActAgentService with mocked deps; we only test tool building."""
    mock_llm = MagicMock()
    mock_rag_tool = MagicMock()
    mock_rag_tool.invoke = AsyncMock(return_value={
        "success": True, "context": "", "sources": [],
    })
    mock_dm_tool = MagicMock()
    mock_dm_tool.invoke = AsyncMock(return_value={
        "success": True, "context": "", "sources": [],
    })
    return ReActAgentService(
        llm_service=mock_llm,
        rag_tool=mock_rag_tool,
        dm_image_query_tool=mock_dm_tool,
    )


def test_per_tool_params_passed_to_rag_tool(service: ReActAgentService):
    """rag_query 的 per-tool top_k 應透過 tool_rag_params 傳遞給底層 invoke。"""
    tools = service._build_builtin_tools(
        tenant_id="t1", kb_id="kb1", kb_ids=["kb1"],
        enabled_tools=["rag_query"],
        rag_top_k=5,                     # bot global default
        rag_score_threshold=0.3,
        metadata={
            "rerank_enabled": True,
            "rerank_model": "haiku",
            "rerank_top_n": 20,
        },
        tool_rag_params={
            "rag_query": {
                "rag_top_k": 3,           # per-tool override
                "rag_score_threshold": 0.25,
                "rerank_enabled": False,
                "rerank_model": "haiku",
                "rerank_top_n": 20,
            },
        },
    )
    assert len(tools) == 1
    rag_tool_fn = tools[0]
    _run(rag_tool_fn.ainvoke({"query": "test"}))
    service._rag_tool.invoke.assert_awaited_once()
    call_kwargs = service._rag_tool.invoke.call_args.kwargs
    assert call_kwargs["top_k"] == 3
    assert call_kwargs["score_threshold"] == 0.25
    assert call_kwargs["rerank_enabled"] is False


def test_per_tool_params_isolated_per_tool(service: ReActAgentService):
    """rag_query 與 query_dm_with_image 各自吃到不同的 top_k。"""
    tools = service._build_builtin_tools(
        tenant_id="t1", kb_id="kb1", kb_ids=None,
        enabled_tools=["rag_query", "query_dm_with_image"],
        rag_top_k=5,
        rag_score_threshold=0.3,
        metadata={},
        tool_rag_params={
            "rag_query": {"rag_top_k": 3},
            "query_dm_with_image": {"rag_top_k": 10},
        },
    )
    assert {t.name for t in tools} == {"rag_query", "query_dm_with_image"}

    for t in tools:
        _run(t.ainvoke({"query": "test"}))

    rag_kwargs = service._rag_tool.invoke.call_args.kwargs
    dm_kwargs = service._dm_image_query_tool.invoke.call_args.kwargs
    assert rag_kwargs["top_k"] == 3
    assert dm_kwargs["top_k"] == 10


def test_per_tool_kb_ids_overrides_bot_global(service: ReActAgentService):
    """rag_query 的 per-tool kb_ids 應覆寫 Bot 全域 kb_ids，
    底層 invoke 拿到的是 per-tool 的 kb_ids。"""
    tools = service._build_builtin_tools(
        tenant_id="t1", kb_id="kb-global", kb_ids=["kb-faq", "kb-dm"],
        enabled_tools=["rag_query", "query_dm_with_image"],
        rag_top_k=5,
        rag_score_threshold=0.3,
        metadata={},
        tool_rag_params={
            "rag_query": {"kb_ids": ["kb-faq"]},
            "query_dm_with_image": {"kb_ids": ["kb-dm"]},
        },
    )
    assert {t.name for t in tools} == {"rag_query", "query_dm_with_image"}
    for t in tools:
        _run(t.ainvoke({"query": "test"}))

    rag_kwargs = service._rag_tool.invoke.call_args.kwargs
    dm_kwargs = service._dm_image_query_tool.invoke.call_args.kwargs
    assert rag_kwargs["kb_ids"] == ["kb-faq"]
    assert rag_kwargs["kb_id"] == "kb-faq"  # 第一個 kb_id 是 single fallback
    assert dm_kwargs["kb_ids"] == ["kb-dm"]
    assert dm_kwargs["kb_id"] == "kb-dm"


def test_missing_per_tool_kb_ids_falls_back_to_bot_global(
    service: ReActAgentService,
):
    """per-tool 沒設 kb_ids → fallback 到 Bot 全域 kb_ids。"""
    tools = service._build_builtin_tools(
        tenant_id="t1", kb_id="kb-global", kb_ids=["kb-faq", "kb-dm"],
        enabled_tools=["rag_query"],
        rag_top_k=5,
        rag_score_threshold=0.3,
        metadata={},
        tool_rag_params={"rag_query": {"rag_top_k": 3}},  # no kb_ids
    )
    _run(tools[0].ainvoke({"query": "test"}))
    rag_kwargs = service._rag_tool.invoke.call_args.kwargs
    assert rag_kwargs["kb_ids"] == ["kb-faq", "kb-dm"]
    assert rag_kwargs["kb_id"] == "kb-global"


def test_missing_tool_rag_params_falls_back_to_flat_args(
    service: ReActAgentService,
):
    """tool_rag_params 為 None 時 fallback 到原本 rag_top_k / metadata。"""
    tools = service._build_builtin_tools(
        tenant_id="t1", kb_id="kb1", kb_ids=None,
        enabled_tools=["rag_query"],
        rag_top_k=7,
        rag_score_threshold=0.4,
        metadata={"rerank_enabled": True, "rerank_model": "x", "rerank_top_n": 15},
        tool_rag_params=None,
    )
    assert len(tools) == 1
    _run(tools[0].ainvoke({"query": "test"}))
    call_kwargs = service._rag_tool.invoke.call_args.kwargs
    assert call_kwargs["top_k"] == 7
    assert call_kwargs["score_threshold"] == 0.4
    assert call_kwargs["rerank_enabled"] is True
    assert call_kwargs["rerank_model"] == "x"
