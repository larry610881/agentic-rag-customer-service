"""發送訊息用例 — 委託 AgentService 處理，支援對話記憶"""

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from src.application.agent.prompt_assembler import assemble as assemble_prompt
from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.bot.repository import BotRepository
from src.domain.conversation.entity import Conversation
from src.domain.conversation.history_strategy import (
    ConversationHistoryStrategy,
    HistoryStrategyConfig,
)
from src.domain.conversation.repository import ConversationRepository
from src.domain.platform.repository import SystemPromptConfigRepository
from src.domain.shared.exceptions import DomainException
from src.domain.tenant.repository import TenantRepository

if TYPE_CHECKING:
    from src.application.observability.rag_evaluation_use_case import (
        RAGEvaluationUseCase,
    )

logger = structlog.get_logger(__name__)

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
        debug: bool = False,
        react_agent_service: AgentService | None = None,
        tenant_repository: TenantRepository | None = None,
        system_prompt_config_repository: SystemPromptConfigRepository | None = None,
        trace_session_factory: Any | None = None,
        rag_evaluation_use_case: "RAGEvaluationUseCase | None" = None,
    ) -> None:
        self._agent_service = agent_service
        self._conversation_repo = conversation_repository
        self._bot_repo = bot_repository
        self._history_strategy = history_strategy
        self._debug = debug
        self._react_agent_service = react_agent_service
        self._tenant_repo = tenant_repository
        self._trace_session_factory = trace_session_factory
        self._sys_prompt_repo = system_prompt_config_repository
        self._eval_use_case = rag_evaluation_use_case

    async def _load_bot_config(
        self, command: SendMessageCommand
    ) -> dict[str, Any]:
        """Resolve Bot config — shared by execute & execute_stream."""
        cfg: dict[str, Any] = {
            "kb_ids": None,
            "system_prompt": None,
            "llm_params": None,
            "kb_id": command.kb_id,
            "history_limit": None,
            "enabled_tools": None,
            "rag_top_k": None,
            "rag_score_threshold": None,
            "show_sources": True,
            "agent_mode": "router",
        }
        if not (command.bot_id and self._bot_repo):
            # No bot — still resolve system prompts from DB
            if self._sys_prompt_repo:
                sys_cfg = await self._sys_prompt_repo.get()
                cfg["system_prompt"] = assemble_prompt(
                    base_prompt=sys_cfg.base_prompt,
                    mode_prompt=sys_cfg.router_mode_prompt,
                )
            return cfg
        bot = await self._bot_repo.find_by_id(command.bot_id)
        if bot is None:
            if self._sys_prompt_repo:
                sys_cfg = await self._sys_prompt_repo.get()
                cfg["system_prompt"] = assemble_prompt(
                    base_prompt=sys_cfg.base_prompt,
                    mode_prompt=sys_cfg.router_mode_prompt,
                )
            return cfg
        if bot.tenant_id != command.tenant_id:
            msg = (
                f"Bot '{command.bot_id}' does not belong "
                f"to tenant '{command.tenant_id}'"
            )
            raise DomainException(msg)
        cfg["kb_ids"] = bot.knowledge_base_ids or None
        if not cfg["kb_id"] and cfg["kb_ids"]:
            cfg["kb_id"] = cfg["kb_ids"][0]
        cfg["system_prompt"] = bot.system_prompt or None
        llm_params: dict = {
            "temperature": bot.llm_params.temperature,
            "max_tokens": bot.llm_params.max_tokens,
            "frequency_penalty": bot.llm_params.frequency_penalty,
        }
        if bot.llm_provider:
            llm_params["provider_name"] = bot.llm_provider
        if bot.llm_model:
            llm_params["model"] = bot.llm_model
        cfg["llm_params"] = llm_params
        cfg["history_limit"] = bot.llm_params.history_limit
        cfg["enabled_tools"] = (
            bot.enabled_tools
            if bot.enabled_tools is not None
            else None
        )
        cfg["rag_top_k"] = bot.llm_params.rag_top_k
        cfg["rag_score_threshold"] = bot.llm_params.rag_score_threshold
        cfg["show_sources"] = bot.show_sources
        cfg["agent_mode"] = bot.agent_mode or "router"
        cfg["mcp_servers"] = [
            {"url": s.url, "name": s.name, "enabled_tools": s.enabled_tools}
            for s in bot.mcp_servers
        ]
        cfg["max_tool_calls"] = bot.max_tool_calls or 5
        cfg["audit_mode"] = getattr(bot, "audit_mode", "minimal")
        cfg["eval_depth"] = getattr(bot, "eval_depth", "off")
        cfg["eval_provider"] = getattr(bot, "eval_provider", "")
        cfg["eval_model"] = getattr(bot, "eval_model", "")

        # Resolve prompt overrides: Bot → SystemPromptConfig → Seed
        base_prompt = ""
        mode_prompt = ""
        if self._sys_prompt_repo:
            sys_cfg = await self._sys_prompt_repo.get()
            base_prompt = bot.base_prompt or sys_cfg.base_prompt
            mode = cfg["agent_mode"]
            if mode == "react":
                mode_prompt = bot.react_prompt or sys_cfg.react_mode_prompt
            else:
                mode_prompt = bot.router_prompt or sys_cfg.router_mode_prompt

        # Pre-assemble the full system prompt (agent services use it directly)
        cfg["system_prompt"] = assemble_prompt(
            bot_prompt=bot.system_prompt,
            mode=cfg["agent_mode"],
            base_prompt=base_prompt,
            mode_prompt=mode_prompt,
        )

        return cfg

    async def _resolve_agent_service(
        self, tenant_id: str, agent_mode: str
    ) -> AgentService:
        """Select agent service based on bot's agent_mode and tenant permissions."""
        if agent_mode == "router":
            return self._agent_service

        # Check tenant allows the requested mode
        if self._tenant_repo:
            tenant = await self._tenant_repo.find_by_id(tenant_id)
            if tenant and agent_mode not in tenant.allowed_agent_modes:
                logger.warning(
                    "agent.mode_fallback",
                    tenant_id=tenant_id,
                    requested_mode=agent_mode,
                    allowed_modes=tenant.allowed_agent_modes,
                    msg="Bot 設定的 agent_mode 不在租戶允許範圍內，降級為 router",
                )
                return self._agent_service

        if self._react_agent_service is None:
            raise DomainException(
                "ReAct agent mode is not available"
            )
        return self._react_agent_service

    async def _resolve_history(
        self,
        history: list | None,
        history_limit: int | None,
    ) -> tuple[list | None, str, str]:
        """Process history via strategy, return (history, ctx, router)."""
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
        return history, history_context, router_context

    async def execute(self, command: SendMessageCommand) -> AgentResponse:
        conversation = await self._load_or_create_conversation(command)

        history = conversation.messages if conversation.messages else None
        metadata = self._extract_metadata(conversation)

        bot_cfg = await self._load_bot_config(command)
        history, history_context, router_context = (
            await self._resolve_history(
                history, bot_cfg["history_limit"]
            )
        )

        agent = await self._resolve_agent_service(
            command.tenant_id, bot_cfg["agent_mode"]
        )

        t0 = time.perf_counter()
        response = await agent.process_message(
            tenant_id=command.tenant_id,
            kb_id=bot_cfg["kb_id"],
            user_message=command.message,
            history=history,
            kb_ids=bot_cfg["kb_ids"],
            system_prompt=bot_cfg["system_prompt"],
            llm_params=bot_cfg["llm_params"],
            metadata=metadata,
            history_context=history_context,
            router_context=router_context,
            enabled_tools=bot_cfg["enabled_tools"],
            rag_top_k=bot_cfg["rag_top_k"],
            rag_score_threshold=bot_cfg["rag_score_threshold"],
            mcp_servers=bot_cfg.get("mcp_servers"),
            max_tool_calls=bot_cfg.get("max_tool_calls", 5),
            audit_mode=bot_cfg.get("audit_mode", "minimal"),
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

        # Fire-and-forget: persist RAG trace
        trace_id = str(uuid4())
        await self._persist_trace(
            tenant_id=command.tenant_id,
            query=command.message,
            tool_calls=response.tool_calls,
            latency_ms=latency_ms,
            chunk_count=len(retrieved_chunks) if retrieved_chunks else 0,
            message_id=None,
            trace_id=trace_id,
            prompt_snapshot=bot_cfg.get("system_prompt") or None,
        )

        # Fire-and-forget: background evaluation
        eval_depth = bot_cfg.get("eval_depth", "off")
        if eval_depth != "off" and self._eval_use_case:
            asyncio.create_task(
                self._run_evaluations(
                    eval_depth=eval_depth,
                    query=command.message,
                    answer=response.answer,
                    sources=response.sources,
                    tool_calls=response.tool_calls,
                    tenant_id=command.tenant_id,
                    trace_id=trace_id,
                    agent_mode=bot_cfg["agent_mode"],
                    eval_provider=bot_cfg.get("eval_provider", ""),
                    eval_model=bot_cfg.get("eval_model", ""),
                )
            )

        return response

    async def execute_stream(
        self, command: SendMessageCommand
    ) -> AsyncIterator[dict[str, Any]]:
        conversation = await self._load_or_create_conversation(command)

        history = conversation.messages if conversation.messages else None
        metadata = self._extract_metadata(conversation)

        bot_cfg = await self._load_bot_config(command)
        history, history_context, router_context = (
            await self._resolve_history(
                history, bot_cfg["history_limit"]
            )
        )

        agent = await self._resolve_agent_service(
            command.tenant_id, bot_cfg["agent_mode"]
        )

        # Stream from agent service
        full_answer = ""
        tool_calls: list[dict[str, Any]] = []
        sources_list: list[dict[str, Any]] = []

        t0 = time.perf_counter()
        async for event in agent.process_message_stream(
            tenant_id=command.tenant_id,
            kb_id=bot_cfg["kb_id"],
            user_message=command.message,
            history=history,
            kb_ids=bot_cfg["kb_ids"],
            system_prompt=bot_cfg["system_prompt"],
            llm_params=bot_cfg["llm_params"],
            metadata=metadata,
            history_context=history_context,
            router_context=router_context,
            enabled_tools=bot_cfg["enabled_tools"],
            rag_top_k=bot_cfg["rag_top_k"],
            rag_score_threshold=bot_cfg["rag_score_threshold"],
            mcp_servers=bot_cfg.get("mcp_servers"),
            max_tool_calls=bot_cfg.get("max_tool_calls", 5),
            audit_mode=bot_cfg.get("audit_mode", "minimal"),
        ):
            if event["type"] == "token":
                full_answer += event["content"]
            elif event["type"] == "tool_calls":
                tool_calls = event.get("tool_calls", [])
            elif event["type"] == "sources":
                sources_list = event.get("sources", [])
            # Non-debug: hide "direct" tool_calls entirely, strip reasoning for others
            if event["type"] == "tool_calls" and not self._debug:
                tcs = event.get("tool_calls", [])
                # "direct" means no tool used — nothing to show
                if all(tc.get("tool_name") == "direct" for tc in tcs):
                    continue
                event = {
                    "type": "tool_calls",
                    "tool_calls": [
                        {"tool_name": tc.get("tool_name", ""), "reasoning": ""}
                        for tc in tcs
                    ],
                }
            # Suppress sources event when bot has show_sources=False
            if event["type"] == "sources" and not bot_cfg["show_sources"]:
                continue
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

        trace_id = str(uuid4())
        await self._persist_trace(
            tenant_id=command.tenant_id,
            query=command.message,
            tool_calls=tool_calls,
            latency_ms=latency_ms,
            chunk_count=len(retrieved_chunks) if retrieved_chunks else 0,
            message_id=None,
            trace_id=trace_id,
            prompt_snapshot=bot_cfg.get("system_prompt") or None,
        )

        # Fire-and-forget: background evaluation
        eval_depth = bot_cfg.get("eval_depth", "off")
        if eval_depth != "off" and self._eval_use_case:
            asyncio.create_task(
                self._run_evaluations(
                    eval_depth=eval_depth,
                    query=command.message,
                    answer=full_answer,
                    sources=sources_list,
                    tool_calls=tool_calls,
                    tenant_id=command.tenant_id,
                    trace_id=trace_id,
                    agent_mode=bot_cfg["agent_mode"],
                    eval_provider=bot_cfg.get("eval_provider", ""),
                    eval_model=bot_cfg.get("eval_model", ""),
                )
            )

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

    async def _persist_trace(
        self,
        tenant_id: str,
        query: str,
        tool_calls: list[dict[str, Any]],
        latency_ms: int,
        chunk_count: int,
        message_id: str | None = None,
        trace_id: str | None = None,
        prompt_snapshot: str | None = None,
    ) -> None:
        """Save RAG trace to DB (fire-and-forget, never raises).

        Uses injected session factory so E2E tests write to test DB,
        not production.
        """
        try:
            from src.infrastructure.db.models.rag_trace_model import RAGTraceModel

            session_factory = self._trace_session_factory
            if session_factory is None:
                return  # No session factory → skip (prevents unit test leakage)

            if trace_id is None:
                trace_id = str(uuid4())
            row = RAGTraceModel(
                id=str(uuid4()),
                trace_id=trace_id,
                query=query[:2000],
                tenant_id=tenant_id,
                message_id=message_id,
                steps=tool_calls,
                total_ms=float(latency_ms),
                chunk_count=chunk_count,
                prompt_snapshot=prompt_snapshot,
            )
            async with session_factory() as session:
                session.add(row)
                await session.commit()
        except Exception:
            logger.warning("trace.persist_failed", exc_info=True)

    async def _run_evaluations(
        self,
        eval_depth: str,
        query: str,
        answer: str,
        sources: list[Any],
        tool_calls: list[dict[str, Any]],
        tenant_id: str,
        trace_id: str,
        agent_mode: str,
        eval_provider: str = "",
        eval_model: str = "",
    ) -> None:
        """Run RAG evaluations in background (fire-and-forget, never raises).

        Uses evaluate_combined() for 1 LLM call instead of up to 3 separate calls.
        Resolves bot-specific eval LLM via DynamicLLMServiceProxy when configured.
        Smart L1 skip: MCP-only scenarios (no RAG sources) skip L1 retrieval metrics.
        """
        try:
            from src.application.observability.rag_evaluation_use_case import (
                RAGEvaluationUseCase,
            )
            from src.infrastructure.db.session_middleware import (
                independent_session_scope,
            )

            assert self._eval_use_case is not None  # noqa: S101

            # Background task: request session is closed.
            # Use independent_session_scope so DynamicLLMServiceFactory
            # gets a fresh DB session to resolve provider settings.
            async with independent_session_scope():
                eval_llm = self._eval_use_case._llm_service
                if eval_provider or eval_model:
                    if hasattr(eval_llm, "resolve_for_bot"):
                        eval_llm = await eval_llm.resolve_for_bot(
                            provider_name=eval_provider,
                            model=eval_model,
                        )
                else:
                    # No eval-specific config: resolve system default
                    if hasattr(eval_llm, "resolve_for_bot"):
                        eval_llm = await eval_llm.resolve_for_bot()
            eval_uc = RAGEvaluationUseCase(llm_service=eval_llm)

            # Parse depth levels
            depth = eval_depth.upper()
            run_l1 = "L1" in depth
            run_l2 = "L2" in depth
            run_l3 = "L3" in depth

            # Determine if we have RAG sources (vs MCP-only)
            has_rag_sources = False
            chunks: list[str] = []
            if sources:
                for s in sources:
                    if isinstance(s, dict):
                        text = s.get("content_snippet") or s.get("content", "")
                    else:
                        text = getattr(s, "content_snippet", "") or getattr(s, "content", "")
                    if text:
                        chunks.append(text)
                        has_rag_sources = True

            # Include MCP tool outputs (non-RAG tools) as context
            for tc in tool_calls:
                tool_output = tc.get("tool_output", "")
                tool_name = tc.get("tool_name", "")
                if tool_name in ("rag_query", "direct"):
                    continue
                if tool_output:
                    chunks.append(f"[{tool_name}] {tool_output}")

            all_context = "\n---\n".join(chunks)

            result = await eval_uc.evaluate_combined(
                query=query,
                answer=answer,
                all_context=all_context,
                chunks=chunks,
                tool_calls=tool_calls,
                run_l1=run_l1,
                run_l2=run_l2,
                run_l3=run_l3,
                has_rag_sources=has_rag_sources,
                agent_mode=agent_mode,
                tenant_id=tenant_id,
                trace_id=trace_id,
            )
            if result.dimensions:
                await self._persist_eval(result)

        except Exception:
            logger.warning("eval.run_failed", exc_info=True)

    async def _persist_eval(self, eval_result: Any) -> None:
        """Persist a single EvalResult to DB (fire-and-forget, never raises)."""
        try:
            from src.infrastructure.db.models.rag_eval_model import RAGEvalModel

            session_factory = self._trace_session_factory
            if session_factory is None:
                return  # No session factory → skip (prevents unit test leakage)

            row = RAGEvalModel(
                id=str(uuid4()),
                eval_id=eval_result.eval_id,
                message_id=eval_result.message_id,
                trace_id=eval_result.trace_id,
                tenant_id=eval_result.tenant_id,
                layer=eval_result.layer,
                dimensions=[
                    {
                        "name": d.name,
                        "score": d.score,
                        "explanation": d.explanation,
                        **({"metadata": d.metadata} if d.metadata else {}),
                    }
                    for d in eval_result.dimensions
                ],
                avg_score=round(eval_result.avg_score, 3),
                model_used=eval_result.model_used,
            )
            async with session_factory() as session:
                session.add(row)
                await session.commit()
        except Exception:
            logger.warning("eval.persist_failed", exc_info=True)

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
