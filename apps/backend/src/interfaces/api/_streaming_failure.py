"""SSE 串流例外的 failed trace 處理（L5，channel parity）。

web / widget（未來任何通路）的 stream 例外分支共用同一份邏輯：
標記 trace 最後節點 failed → 持久化 trace → 回傳 trace_id 供 done 事件帶給前端。
原本只有 agent_router 有做，widget 通路的失敗完全不出現在
agent_execution_traces / Studio 觀測頁，該輪 trace 直接丟失。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def persist_failed_stream_trace(
    use_case: Any,
    *,
    conversation_id: str | None,
    source: str,
    error_msg: str,
    persist: bool = True,
) -> str:
    """標記當前 trace failed 並持久化；回傳 trace_id（無 trace 時空字串）。"""
    from src.infrastructure.observability.agent_trace_collector import (
        AgentTraceCollector,
    )

    AgentTraceCollector.mark_current_failed(error_msg)

    trace = AgentTraceCollector.current()
    if trace is None:
        return ""
    try:
        await use_case._persist_agent_trace(  # noqa: SLF001
            conversation_id=conversation_id,
            message_id=None,
            latency_ms=0,
            source=source,
            persist=persist,
        )
    except Exception:
        logger.exception("stream.persist_failed_trace_error")
    return trace.trace_id
