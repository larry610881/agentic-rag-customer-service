"""發送訊息用例 — 委託 AgentService 處理，支援對話記憶"""

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.bot.repository import BotRepository
from src.domain.conversation.entity import Conversation, Message
from src.domain.shared.exceptions import DomainException
from src.domain.conversation.history_strategy import (
    ConversationHistoryStrategy,
    HistoryStrategyConfig,
)
from src.domain.conversation.repository import ConversationRepository

_REFUND_METADATA_MARKER = "__refund_metadata"


@dataclass(frozen=True)
class SendMessageCommand:
    tenant_id: str
    kb_id: str = ""
    message: str = ""
    conversation_id: str | None = None
    bot_id: str | None = None


class SendMessageUseCase:
    def __init__(
        self,
        agent_service: AgentService,
        conversation_repository: ConversationRepository,
        bot_repository: BotRepository | None = None,
        history_strategy: ConversationHistoryStrategy | None = None,
    ) -> None:
        self._agent_service = agent_service
        self._conversation_repo = conversation_repository
        self._bot_repo = bot_repository
        self._history_strategy = history_strategy

    async def execute(self, command: SendMessageCommand) -> AgentResponse:
        conversation = await self._load_or_create_conversation(command)

        history = conversation.messages if conversation.messages else None
        metadata = self._extract_metadata(conversation)

        # Resolve Bot config if bot_id is provided
        kb_ids: list[str] | None = None
        system_prompt: str | None = None
        llm_params: dict[str, Any] | None = None
        kb_id = command.kb_id
        history_limit: int | None = None
        enabled_tools: list[str] | None = None
        rag_top_k: int | None = None
        rag_score_threshold: float | None = None

        if command.bot_id and self._bot_repo:
            bot = await self._bot_repo.find_by_id(command.bot_id)
            if bot is not None:
                if bot.tenant_id != command.tenant_id:
                    raise DomainException(
                        f"Bot '{command.bot_id}' does not belong to tenant '{command.tenant_id}'"
                    )
                kb_ids = bot.knowledge_base_ids or None
                if not kb_id and kb_ids:
                    kb_id = kb_ids[0]
                system_prompt = bot.system_prompt or None
                llm_params = {
                    "temperature": bot.llm_params.temperature,
                    "max_tokens": bot.llm_params.max_tokens,
                    "frequency_penalty": bot.llm_params.frequency_penalty,
                }
                history_limit = bot.llm_params.history_limit
                # [] means "no tools" (direct LLM), None means "all tools"
                enabled_tools = bot.enabled_tools if bot.enabled_tools is not None else None
                rag_top_k = bot.llm_params.rag_top_k
                rag_score_threshold = bot.llm_params.rag_score_threshold

        # Process history via strategy
        history_context = ""
        router_context = ""
        if self._history_strategy and history:
            strategy_config = HistoryStrategyConfig(
                history_limit=history_limit or 10,
                recent_turns=3,
            )
            ctx = await self._history_strategy.process(
                history, strategy_config
            )
            history_context = ctx.respond_context
            router_context = ctx.router_context
        elif history and history_limit is not None:
            history = history[-history_limit:]

        t0 = time.perf_counter()
        response = await self._agent_service.process_message(
            tenant_id=command.tenant_id,
            kb_id=kb_id,
            user_message=command.message,
            history=history,
            kb_ids=kb_ids,
            system_prompt=system_prompt,
            llm_params=llm_params,
            metadata=metadata,
            history_context=history_context,
            router_context=router_context,
            enabled_tools=enabled_tools,
            rag_top_k=rag_top_k,
            rag_score_threshold=rag_score_threshold,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)

        retrieved_chunks = (
            [s.to_dict() for s in response.sources]
            if response.sources
            else None
        )

        tool_calls_to_save = response.tool_calls[:]
        if response.refund_step:
            tool_calls_to_save.append(
                {
                    "tool_name": _REFUND_METADATA_MARKER,
                    "refund_step": response.refund_step,
                }
            )

        conversation.add_message("user", command.message)
        conversation.add_message(
            "assistant",
            response.answer,
            tool_calls=tool_calls_to_save,
            latency_ms=latency_ms,
            retrieved_chunks=retrieved_chunks,
        )
        await self._conversation_repo.save(conversation)

        response.conversation_id = conversation.id.value
        return response

    async def execute_stream(
        self, command: SendMessageCommand
    ) -> AsyncIterator[dict[str, Any]]:
        conversation = await self._load_or_create_conversation(command)

        history = conversation.messages if conversation.messages else None
        metadata = self._extract_metadata(conversation)

        # Resolve Bot config (same as execute)
        kb_ids: list[str] | None = None
        system_prompt: str | None = None
        llm_params: dict[str, Any] | None = None
        kb_id = command.kb_id
        history_limit: int | None = None
        enabled_tools: list[str] | None = None
        rag_top_k: int | None = None
        rag_score_threshold: float | None = None

        if command.bot_id and self._bot_repo:
            bot = await self._bot_repo.find_by_id(command.bot_id)
            if bot is not None:
                if bot.tenant_id != command.tenant_id:
                    raise DomainException(
                        f"Bot '{command.bot_id}' does not belong to tenant '{command.tenant_id}'"
                    )
                kb_ids = bot.knowledge_base_ids or None
                if not kb_id and kb_ids:
                    kb_id = kb_ids[0]
                system_prompt = bot.system_prompt or None
                llm_params = {
                    "temperature": bot.llm_params.temperature,
                    "max_tokens": bot.llm_params.max_tokens,
                    "frequency_penalty": bot.llm_params.frequency_penalty,
                }
                history_limit = bot.llm_params.history_limit
                # [] means "no tools" (direct LLM), None means "all tools"
                enabled_tools = bot.enabled_tools if bot.enabled_tools is not None else None
                rag_top_k = bot.llm_params.rag_top_k
                rag_score_threshold = bot.llm_params.rag_score_threshold

        # Process history via strategy
        history_context = ""
        router_context = ""
        if self._history_strategy and history:
            strategy_config = HistoryStrategyConfig(
                history_limit=history_limit or 10,
                recent_turns=3,
            )
            ctx = await self._history_strategy.process(
                history, strategy_config
            )
            history_context = ctx.respond_context
            router_context = ctx.router_context
        elif history and history_limit is not None:
            history = history[-history_limit:]

        # Stream from agent service
        full_answer = ""
        tool_calls: list[dict[str, Any]] = []
        sources_list: list[dict[str, Any]] = []

        t0 = time.perf_counter()
        async for event in self._agent_service.process_message_stream(
            tenant_id=command.tenant_id,
            kb_id=kb_id,
            user_message=command.message,
            history=history,
            kb_ids=kb_ids,
            system_prompt=system_prompt,
            llm_params=llm_params,
            metadata=metadata,
            history_context=history_context,
            router_context=router_context,
            enabled_tools=enabled_tools,
            rag_top_k=rag_top_k,
            rag_score_threshold=rag_score_threshold,
        ):
            if event["type"] == "token":
                full_answer += event["content"]
            elif event["type"] == "tool_calls":
                tool_calls = event.get("tool_calls", [])
            elif event["type"] == "sources":
                sources_list = event.get("sources", [])
            yield event
        latency_ms = int((time.perf_counter() - t0) * 1000)

        retrieved_chunks = sources_list if sources_list else None

        # Save conversation after streaming completes
        conversation.add_message("user", command.message)
        conversation.add_message(
            "assistant",
            full_answer,
            tool_calls=tool_calls,
            latency_ms=latency_ms,
            retrieved_chunks=retrieved_chunks,
        )
        await self._conversation_repo.save(conversation)

        yield {
            "type": "conversation_id",
            "conversation_id": conversation.id.value,
        }
        yield {"type": "done"}

    async def _load_or_create_conversation(
        self, command: SendMessageCommand
    ) -> Conversation:
        if command.conversation_id:
            existing = await self._conversation_repo.find_by_id(
                command.conversation_id
            )
            if existing is not None:
                return existing

        return Conversation(tenant_id=command.tenant_id, bot_id=command.bot_id)

    @staticmethod
    def _extract_metadata(conversation: Conversation) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for msg in reversed(conversation.messages):
            if msg.role == "assistant":
                for tc in msg.tool_calls:
                    if tc.get("tool_name") == _REFUND_METADATA_MARKER:
                        refund_step = tc.get("refund_step")
                        if refund_step:
                            metadata["refund_step"] = refund_step
                break
        return metadata
