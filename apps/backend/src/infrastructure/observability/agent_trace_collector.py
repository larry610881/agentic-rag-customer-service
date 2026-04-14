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


class AgentTraceCollector:
    """Request-scoped agent execution trace collector."""

    @staticmethod
    def start(
        tenant_id: str,
        agent_mode: str,
        message_id: str | None = None,
        conversation_id: str | None = None,
    ) -> AgentExecutionTrace:
        trace = AgentExecutionTrace(
            tenant_id=tenant_id,
            agent_mode=agent_mode,
            message_id=message_id,
            conversation_id=conversation_id,
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
        **metadata: Any,
    ) -> str:
        """Add a node to the current trace. Returns node_id."""
        trace = _agent_trace.get()
        if trace is None:
            return ""
        return trace.add_node(
            node_type=node_type,
            label=label,
            parent_id=parent_id,
            start_ms=start_ms,
            end_ms=end_ms,
            token_usage=token_usage,
            **metadata,
        )

    @staticmethod
    def finish(total_ms: float) -> AgentExecutionTrace | None:
        """Finish and return the trace, then clear ContextVar."""
        trace = _agent_trace.get()
        _agent_trace.set(None)
        _trace_t0.set(0.0)
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
    def current() -> AgentExecutionTrace | None:
        return _agent_trace.get()
