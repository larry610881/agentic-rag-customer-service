"""SupervisorAgentService — Multi-Agent 調度器（含情緒偵測 + 反思）"""

from collections.abc import AsyncIterator
from uuid import uuid4

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService, SentimentService
from src.domain.agent.worker import AgentWorker, WorkerContext
from src.domain.conversation.entity import Message
from src.domain.rag.value_objects import TokenUsage

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
        )

        response = await self._dispatch(context)

        response = self._reflect(response, context)

        if sentiment_result:
            response.sentiment = sentiment_result.sentiment
            response.escalated = sentiment_result.should_escalate

        return response

    async def _dispatch(self, context: WorkerContext) -> AgentResponse:
        for worker in self._workers:
            if await worker.can_handle(context):
                result = await worker.handle(context)
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
    ) -> AsyncIterator[str]:
        response = await self.process_message(
            tenant_id, kb_id, user_message, history
        )
        for char in response.answer:
            yield char
