"""Agent Execution Trace — 記錄完整 Agent 編排鏈路

Domain Value Objects for capturing the full agent execution graph:
user_input → routing → sub-agent → tool calls → final response.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class ExecutionNode:
    """DAG 中的單一節點"""

    node_id: str = field(default_factory=lambda: str(uuid4()))
    node_type: str = ""  # user_input | router | meta_router | supervisor_dispatch
    # agent_llm | tool_call | tool_result | final_response | worker_execution | error
    label: str = ""
    parent_id: str | None = None
    start_ms: float = 0.0  # 相對於 trace 起點
    end_ms: float = 0.0
    duration_ms: float = 0.0
    token_usage: dict[str, Any] | None = None
    # Phase 1: 失敗節點視覺化的 source of truth。"success" / "failed" / "partial"。
    # error_message 當 outcome=="failed" 時放在 metadata["error_message"]。
    outcome: str = "success"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "parent_id": self.parent_id,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "token_usage": self.token_usage,
            "outcome": self.outcome,
            "metadata": self.metadata,
        }


@dataclass
class AgentExecutionTrace:
    """完整的 Agent 執行追蹤記錄（flat adjacency list）"""

    trace_id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    message_id: str | None = None
    conversation_id: str | None = None
    agent_mode: str = ""  # react | supervisor | meta_supervisor
    source: str = ""  # web | widget | line
    llm_model: str = ""
    llm_provider: str = ""
    bot_id: str | None = None
    nodes: list[ExecutionNode] = field(default_factory=list)
    total_ms: float = 0.0
    total_tokens: dict[str, Any] | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def add_node(
        self,
        node_type: str,
        label: str,
        parent_id: str | None,
        start_ms: float,
        end_ms: float,
        token_usage: dict[str, Any] | None = None,
        outcome: str = "success",
        **metadata: Any,
    ) -> str:
        """Add a node and return its node_id."""
        node = ExecutionNode(
            node_type=node_type,
            label=label,
            parent_id=parent_id,
            start_ms=round(start_ms, 1),
            end_ms=round(end_ms, 1),
            duration_ms=round(end_ms - start_ms, 1),
            token_usage=token_usage,
            outcome=outcome,
            metadata=metadata,
        )
        self.nodes.append(node)
        return node.node_id

    def finish(self, total_ms: float) -> None:
        self.total_ms = round(total_ms, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "agent_mode": self.agent_mode,
            "source": self.source,
            "nodes": [n.to_dict() for n in self.nodes],
            "total_ms": self.total_ms,
            "total_tokens": self.total_tokens,
            "created_at": self.created_at.isoformat(),
        }
