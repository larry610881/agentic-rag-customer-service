"""AgentTraceCollector — ContextVar-scoped collector for agent execution traces.

Same pattern as RAGTracer: request-scoped via ContextVar,
called from within agent services during execution.
"""

import time
from contextvars import ContextVar
from typing import Any

import structlog

from src.domain.observability.agent_trace import AgentExecutionTrace

logger = structlog.get_logger(__name__)

_agent_trace: ContextVar[AgentExecutionTrace | None] = ContextVar(
    "_agent_trace", default=None
)
_trace_t0: ContextVar[float] = ContextVar("_trace_t0", default=0.0)
_current_tool_node_id: ContextVar[str] = ContextVar(
    "_current_tool_node_id", default=""
)
# Phase 1: 最近一次 add_node() 寫入的 node_id；
# 11 處 stream yield 點用 last_node_id() 一行帶進事件 dict，
# 取代 MVP 的 event.type→tool_name 啟發式對應。
_last_node_id: ContextVar[str] = ContextVar("_last_node_id", default="")


class AgentTraceCollector:
    """Request-scoped agent execution trace collector."""

    @staticmethod
    def start(
        tenant_id: str,
        agent_mode: str,
        message_id: str | None = None,
        conversation_id: str | None = None,
        llm_model: str = "",
        llm_provider: str = "",
        bot_id: str | None = None,
    ) -> AgentExecutionTrace:
        # Idempotent：若 caller 已先 start（例如 use case 為了讓 guard
        # node 有 active trace），agent_service 後來再 start 一次時不該
        # 重置 trace。Return 現有 trace，但補強空欄位（agent_service 通常
        # 帶得到較完整的 model/mode 資訊）
        existing = _agent_trace.get()
        if existing is not None:
            if not existing.agent_mode and agent_mode:
                existing.agent_mode = agent_mode
            if not existing.llm_model and llm_model:
                existing.llm_model = llm_model
            if not existing.llm_provider and llm_provider:
                existing.llm_provider = llm_provider
            if not existing.bot_id and bot_id:
                existing.bot_id = bot_id
            return existing

        trace = AgentExecutionTrace(
            tenant_id=tenant_id,
            agent_mode=agent_mode,
            message_id=message_id,
            conversation_id=conversation_id,
            llm_model=llm_model,
            llm_provider=llm_provider,
            bot_id=bot_id,
        )
        _agent_trace.set(trace)
        _trace_t0.set(time.monotonic())
        logger.debug(
            "agent_trace.start",
            trace_id=trace.trace_id,
            agent_mode=agent_mode,
        )
        return trace

    @staticmethod
    def offset_ms() -> float:
        """Current offset in ms from trace start."""
        t0 = _trace_t0.get(0.0)
        if t0 == 0.0:
            return 0.0
        return (time.monotonic() - t0) * 1000

    @staticmethod
    def add_node(
        node_type: str,
        label: str,
        parent_id: str | None,
        start_ms: float,
        end_ms: float,
        token_usage: dict[str, Any] | None = None,
        outcome: str = "success",
        **metadata: Any,
    ) -> str:
        """Add a node to the current trace. Returns node_id.
        同時更新 ContextVar `_last_node_id`，讓 stream yield 端可零負擔取用。
        """
        trace = _agent_trace.get()
        if trace is None:
            return ""
        node_id = trace.add_node(
            node_type=node_type,
            label=label,
            parent_id=parent_id,
            start_ms=start_ms,
            end_ms=end_ms,
            token_usage=token_usage,
            outcome=outcome,
            **metadata,
        )
        if node_id:
            _last_node_id.set(node_id)
        return node_id

    @staticmethod
    def last_node_id() -> str:
        """取得最近 add_node() 的 node_id（無 trace 時回空字串）。"""
        return _last_node_id.get("")

    @staticmethod
    def mark_current_failed(error_message: str) -> None:
        """把最近一筆節點標記為 failed，並把 error_message 寫進 metadata。
        若無 trace 或 last_node_id 不存在於 trace.nodes，靜默跳過。
        """
        trace = _agent_trace.get()
        if trace is None:
            return
        target_id = _last_node_id.get("")
        if not target_id:
            return
        for node in trace.nodes:
            if node.node_id == target_id:
                node.outcome = "failed"
                node.metadata["error_message"] = error_message
                return

    @staticmethod
    def finish(total_ms: float) -> AgentExecutionTrace | None:
        """Finish and return the trace, then clear ContextVar."""
        trace = _agent_trace.get()
        _agent_trace.set(None)
        _trace_t0.set(0.0)
        _last_node_id.set("")
        if trace is None:
            return None
        trace.finish(total_ms)
        logger.info(
            "agent_trace.finish",
            trace_id=trace.trace_id,
            agent_mode=trace.agent_mode,
            total_ms=trace.total_ms,
            node_count=len(trace.nodes),
        )
        return trace

    @staticmethod
    def set_tool_parent(node_id: str) -> None:
        """Set current tool node ID so inner nodes can use it as parent."""
        _current_tool_node_id.set(node_id)

    @staticmethod
    def clear_tool_parent() -> None:
        _current_tool_node_id.set("")

    @staticmethod
    def tool_parent() -> str | None:
        """Get current tool parent node ID, or None if not set."""
        val = _current_tool_node_id.get("")
        return val or None

    @staticmethod
    def find_last_node_by(node_type: str, label: str) -> str | None:
        """找最近一筆 node_type + label 都吻合的節點 id，無則回 None。

        用途：RAG 等「inner tool result」要 attach 到對應的 tool_call 節點時，
        不能依賴 ContextVar 的 tool_parent()（單值會被 LLM parallel tool calls
        覆蓋成「最後一個」tool 的 nid）。改用 label 反查最近一筆對應 tool_call，
        確保 parent 永遠指向真正的呼叫者。
        """
        trace = _agent_trace.get()
        if trace is None:
            return None
        for node in reversed(trace.nodes):
            if node.node_type == node_type and node.label == label:
                return node.node_id
        return None

    @staticmethod
    def current() -> AgentExecutionTrace | None:
        return _agent_trace.get()
