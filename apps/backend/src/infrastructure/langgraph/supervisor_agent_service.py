"""SupervisorAgentService — Multi-Agent 調度器（含情緒偵測 + 反思）"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService, SentimentService
from src.domain.agent.worker import AgentWorker, WorkerContext
from src.domain.conversation.entity import Message
from src.domain.rag.value_objects import TokenUsage
from src.infrastructure.langgraph.usage import build_usage_event
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

_MIN_ANSWER_LENGTH = 10


class SupervisorAgentService(AgentService):
    def __init__(
        self,
        workers: list[AgentWorker],
        sentiment_service: SentimentService | None = None,
    ) -> None:
        self._workers = workers
        self._sentiment_service = sentiment_service

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
        metadata: dict[str, Any] | None = None,
        history_context: str = "",
        router_context: str = "",
        enabled_tools: list[str] | None = None,
        rag_top_k: int | None = None,
        rag_score_threshold: float | None = None,
    ) -> AgentResponse:
        AgentTraceCollector.start(tenant_id, "supervisor")
        AgentTraceCollector.add_node(
            "user_input", "使用者輸入", None, 0.0, 0.0,
            message_preview=user_message[:200],
        )

        sentiment_result = None
        if self._sentiment_service:
            sentiment_result = await self._sentiment_service.analyze(
                user_message
            )

        context = WorkerContext(
            tenant_id=tenant_id,
            kb_id=kb_id,
            user_message=user_message,
            conversation_history=history or [],
            metadata=metadata or {},
        )

        response = await self._dispatch(context)
        response = self._reflect(response, context)

        if sentiment_result:
            response.sentiment = sentiment_result.sentiment
            response.escalated = sentiment_result.should_escalate

        end_ms = AgentTraceCollector.offset_ms()
        AgentTraceCollector.add_node(
            "final_response", "最終回覆", None, end_ms, end_ms,
            sentiment=sentiment_result.sentiment if sentiment_result else None,
            escalated=sentiment_result.should_escalate if sentiment_result else False,
        )

        return response

    async def _dispatch(self, context: WorkerContext) -> AgentResponse:
        for worker in self._workers:
            if await worker.can_handle(context):
                t0_ms = AgentTraceCollector.offset_ms()
                AgentTraceCollector.add_node(
                    "supervisor_dispatch", f"選擇 {worker.name}", None,
                    t0_ms, t0_ms,
                    selected_worker=worker.name,
                )
                t_exec = AgentTraceCollector.offset_ms()
                result = await worker.handle(context)
                AgentTraceCollector.add_node(
                    "worker_execution", worker.name, None,
                    t_exec, AgentTraceCollector.offset_ms(),
                )
                return AgentResponse(
                    answer=result.answer,
                    tool_calls=result.tool_calls,
                    sources=result.sources,
                    conversation_id=str(uuid4()),
                    usage=result.usage or TokenUsage.zero("fake"),
                    refund_step=result.metadata.get("refund_step"),
                )

        return AgentResponse(
            answer="抱歉，我無法處理您的請求。",
            conversation_id=str(uuid4()),
            usage=TokenUsage.zero("fake"),
        )

    def _reflect(
        self, response: AgentResponse, context: WorkerContext
    ) -> AgentResponse:
        if len(response.answer) < _MIN_ANSWER_LENGTH:
            response.answer = (
                f"關於您的問題「{context.user_message}」，"
                f"{response.answer}"
                "如需更多協助，請告訴我。"
            )
        return response

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
    ) -> AsyncIterator[dict[str, Any]]:
        response = await self.process_message(
            tenant_id, kb_id, user_message, history,
            metadata=metadata,
        )
        yield {"type": "token", "content": response.answer}
        if response.sources:
            yield {
                "type": "sources",
                "sources": [s.to_dict() for s in response.sources],
            }
        usage_event = build_usage_event(response.usage)
        if usage_event:
            yield usage_event
