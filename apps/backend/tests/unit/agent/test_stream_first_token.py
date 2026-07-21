"""串流路徑 TTFT（首 token 時間）trace 節點測試（Issue #49 方法 B）

背景：LINE 為非串流整包回覆，web 為串流。為量化「web 體感 vs LINE 體感」
差距，串流路徑在每輪生成的第一個 token 抵達時記一個零長度
`first_token` trace 節點（start_ms = 距請求開始的毫秒數）。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from src.infrastructure.langgraph.react_agent_service import ReActAgentService
from src.infrastructure.langgraph.tools import RAGQueryTool
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_mock_llm(side_effects: list[AIMessage]):
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke = AsyncMock(side_effect=side_effects)
    return mock_llm


def _make_rag_tool():
    @tool
    async def rag_query(query: str) -> str:
        """查詢知識庫回答用戶問題。

        Args:
            query: 要查詢的問題
        """
        return "知識庫結果"

    return rag_query


def _build_service():
    llm_service = AsyncMock()
    rag_tool = AsyncMock(spec=RAGQueryTool)
    cached_tool_loader = MagicMock()
    cached_tool_loader.load_tools = AsyncMock(return_value=[])
    return ReActAgentService(
        llm_service=llm_service,
        rag_tool=rag_tool,
        cached_tool_loader=cached_tool_loader,
    )


def test_stream_records_first_token_trace_node(monkeypatch):
    """串流完成後，trace 應含 first_token 節點（含迭代編號）。"""
    service = _build_service()
    mock_llm = _make_mock_llm([
        AIMessage(
            content="",
            tool_calls=[
                {"name": "rag_query", "args": {"query": "q"}, "id": "call_1"},
            ],
        ),
        AIMessage(content="根據查詢結果，這是回答。"),
    ])
    monkeypatch.setattr(
        service, "_resolve_llm_model", AsyncMock(return_value=mock_llm)
    )
    monkeypatch.setattr(
        service,
        "_build_builtin_tools",
        lambda **kwargs: [_make_rag_tool()],
    )

    async def _collect():
        AgentTraceCollector.start(tenant_id="t-ttft", agent_mode="react")
        events = []
        async for ev in service.process_message_stream(
            tenant_id="t-ttft",
            kb_id="kb-1",
            user_message="測試",
        ):
            events.append(ev)
        trace = AgentTraceCollector.finish(total_ms=1.0)
        return events, trace

    events, trace = _run(_collect())

    assert trace is not None
    ft_nodes = [n for n in trace.nodes if n.node_type == "first_token"]
    assert ft_nodes, (
        f"應記錄 first_token 節點，實際節點: "
        f"{[n.node_type for n in trace.nodes]}"
    )
    node = ft_nodes[0]
    assert node.start_ms == node.end_ms  # 零長度時間戳節點
    assert node.metadata.get("iteration") == 2  # tool call 後的生成輪
    # 事件流本身不受影響：仍有 token 事件
    assert any(e.get("type") == "token" for e in events)
