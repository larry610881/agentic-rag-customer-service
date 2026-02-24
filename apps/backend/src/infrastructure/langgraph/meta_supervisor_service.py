"""MetaSupervisorService — 頂層路由，依 user_role 到對應 Team"""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService, SentimentService
from src.domain.agent.team_supervisor import TeamSupervisor
from src.domain.agent.worker import WorkerContext
from src.domain.conversation.entity import Message
from src.domain.rag.value_objects import TokenUsage

_MIN_ANSWER_LENGTH = 10
_DEFAULT_ROLE = "customer"


class MetaSupervisorService(AgentService):
    """頂層路由：依 user_role dispatch 到對應 TeamSupervisor。

    行為與 SupervisorAgentService 一致（情緒偵測 + 反思），
    但增加角色級路由。
    """

    def __init__(
        self,
        teams: dict[str, TeamSupervisor],
        sentiment_service: SentimentService | None = None,
    ) -> None:
        self._teams = teams
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
        user_role: str = _DEFAULT_ROLE,
        metadata: dict[str, Any] | None = None,
        history_context: str = "",
        router_context: str = "",
    ) -> AgentResponse:
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
            user_role=user_role,
            metadata=metadata or {},
        )

        response = await self._dispatch(context)
        response = self._reflect(response, context)

        if sentiment_result:
            response.sentiment = sentiment_result.sentiment
            response.escalated = sentiment_result.should_escalate

        return response

    async def _dispatch(self, context: WorkerContext) -> AgentResponse:
        team = self._teams.get(
            context.user_role,
            self._teams.get(_DEFAULT_ROLE),
        )

        if team is None:
            return AgentResponse(
                answer="抱歉，我無法處理您的請求。",
                conversation_id=str(uuid4()),
                usage=TokenUsage.zero("meta-supervisor"),
            )

        result = await team.handle(context)
        return AgentResponse(
            answer=result.answer,
            tool_calls=result.tool_calls,
            sources=result.sources,
            conversation_id=str(uuid4()),
            usage=result.usage or TokenUsage.zero("meta-supervisor"),
            refund_step=result.metadata.get("refund_step"),
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
    ) -> AsyncIterator[str]:
        response = await self.process_message(
            tenant_id, kb_id, user_message, history
        )
        for char in response.answer:
            yield char
