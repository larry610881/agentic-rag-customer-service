"""MetaSupervisorService — 頂層路由，依 user_role 到對應 Team"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.agent.team_supervisor import TeamSupervisor
from src.domain.agent.worker import WorkerContext
from src.domain.conversation.entity import Message
from src.domain.rag.value_objects import TokenUsage
from src.infrastructure.langgraph.usage import build_usage_event
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

_DEFAULT_ROLE = "customer"


class MetaSupervisorService(AgentService):
    """頂層路由：依 user_role dispatch 到對應 TeamSupervisor。"""

    def __init__(
        self,
        teams: dict[str, TeamSupervisor],
    ) -> None:
        self._teams = teams

    async def process_message(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
        *,
        kb_ids: list[str] | None = None,
        system_prompt: str | None = None,
        llm_params: dict[str, Any] | None = None,
        user_role: str = _DEFAULT_ROLE,
        metadata: dict[str, Any] | None = None,
        history_context: str = "",
        router_context: str = "",
        enabled_tools: list[str] | None = None,
        rag_top_k: int | None = None,
        rag_score_threshold: float | None = None,
        tool_rag_params: dict[str, dict[str, Any]] | None = None,
        customer_service_url: str = "",
        mcp_servers: list[dict[str, Any]] | None = None,
        max_tool_calls: int = 5,
    ) -> AgentResponse:
        _llm_params = llm_params or {}
        AgentTraceCollector.start(
            tenant_id, "meta_supervisor",
            llm_model=_llm_params.get("model", ""),
            llm_provider=_llm_params.get("provider_name", ""),
            bot_id=_llm_params.get("bot_id") or None,
        )
        AgentTraceCollector.add_node(
            "user_input", "使用者輸入", None, 0.0, 0.0,
            message_preview=user_message[:200],
        )

        context = WorkerContext(
            tenant_id=tenant_id,
            kb_id=kb_id,
            user_message=user_message,
            conversation_history=history or [],
            user_role=user_role,
            metadata=metadata or {},
        )

        response = await self._dispatch(context)

        end_ms = AgentTraceCollector.offset_ms()
        AgentTraceCollector.add_node(
            "final_response", "最終回覆", None, end_ms, end_ms,
        )

        return response

    async def _dispatch(self, context: WorkerContext) -> AgentResponse:
        team = self._teams.get(
            context.user_role,
            self._teams.get(_DEFAULT_ROLE),
        )

        t_route = AgentTraceCollector.offset_ms()
        selected_team = team.name if team else "(none)"
        AgentTraceCollector.add_node(
            "meta_router", f"路由至 {selected_team}", None,
            t_route, AgentTraceCollector.offset_ms(),
            user_role=context.user_role,
            selected_team=selected_team,
        )

        if team is None:
            return AgentResponse(
                answer="抱歉，我無法處理您的請求。",
                conversation_id=str(uuid4()),
                usage=TokenUsage.zero("meta-supervisor"),
            )

        t_exec = AgentTraceCollector.offset_ms()
        result = await team.handle(context)
        AgentTraceCollector.add_node(
            "worker_execution", team.name, None,
            t_exec, AgentTraceCollector.offset_ms(),
        )
        return AgentResponse(
            answer=result.answer,
            tool_calls=result.tool_calls,
            sources=result.sources,
            conversation_id=str(uuid4()),
            usage=result.usage or TokenUsage.zero("meta-supervisor"),
            refund_step=result.metadata.get("refund_step"),
        )

    async def process_message_stream(
        self,
        tenant_id: str,
        kb_id: str,
        user_message: str,
        history: list[Message] | None = None,
        *,
        kb_ids: list[str] | None = None,
        system_prompt: str | None = None,
        llm_params: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        history_context: str = "",
        router_context: str = "",
        enabled_tools: list[str] | None = None,
        rag_top_k: int | None = None,
        rag_score_threshold: float | None = None,
        tool_rag_params: dict[str, dict[str, Any]] | None = None,
        customer_service_url: str = "",
        mcp_servers: list[dict[str, Any]] | None = None,
        max_tool_calls: int = 5,
    ) -> AsyncIterator[dict[str, Any]]:
        response = await self.process_message(
            tenant_id, kb_id, user_message, history,
            metadata=metadata,
        )
        # Yield tool_calls so execute_stream can persist them
        if response.tool_calls:
            yield {"type": "tool_calls", "tool_calls": response.tool_calls}
        # Yield refund_step metadata
        if response.refund_step:
            yield {"type": "refund_step", "refund_step": response.refund_step}
        yield {"type": "token", "content": response.answer}
        if response.sources:
            yield {
                "type": "sources",
                "sources": [s.to_dict() for s in response.sources],
            }
        usage_event = build_usage_event(response.usage)
        if usage_event:
            yield usage_event
