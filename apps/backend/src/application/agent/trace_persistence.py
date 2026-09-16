"""Agent trace 持久化（web / widget / LINE 共用；channel-parity 債務第 2 項）。

原本 send_message_use_case 與 handle_webhook_use_case 各有一份寫
agent_execution_traces 的程式碼，欄位對齊靠人眼（M20 就是 LINE 漏了 outcome）。
現在只有這一份。
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4


def compute_trace_outcome(nodes: list[dict[str, Any]]) -> str:
    """S-Gov.6a: 從節點 outcome 計算 trace-level outcome。

    優先級：failed > partial > success。
    """
    if any(n.get("outcome") == "failed" for n in nodes):
        return "failed"
    if any(n.get("outcome") == "partial" for n in nodes):
        return "partial"
    return "success"


async def persist_finished_trace(
    trace: Any,
    session_factory: Any,
    *,
    conversation_id: str | None,
    message_id: str | None,
    source: str | None = None,
) -> str | None:
    """把已 `finish()` 的 trace 寫進 agent_execution_traces；回傳 trace_id。

    trace 或 session_factory 缺席 → 不寫（回 None）。不吞例外，由呼叫端決定
    fail-open 的 log。
    """
    if trace is None or session_factory is None:
        return None
    if source:
        trace.source = source
    trace.conversation_id = conversation_id
    trace.message_id = message_id

    from src.infrastructure.db.models.agent_trace_model import (
        AgentExecutionTraceModel,
    )

    node_dicts = [n.to_dict() for n in trace.nodes]
    row = AgentExecutionTraceModel(
        id=str(uuid4()),
        trace_id=trace.trace_id,
        tenant_id=trace.tenant_id,
        message_id=trace.message_id,
        conversation_id=trace.conversation_id,
        agent_mode=trace.agent_mode,
        source=trace.source,
        llm_model=trace.llm_model,
        llm_provider=trace.llm_provider,
        bot_id=trace.bot_id,
        nodes=node_dicts,
        total_ms=trace.total_ms,
        total_tokens=trace.total_tokens,
        outcome=compute_trace_outcome(node_dicts),
        config_hash=trace.config_hash,
        abuse_level=trace.abuse_level,
    )
    async with session_factory() as session:
        session.add(row)
        await session.commit()
    return str(trace.trace_id)
