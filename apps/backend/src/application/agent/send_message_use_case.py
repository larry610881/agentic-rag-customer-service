"""發送訊息用例 — 委託 AgentService 處理，支援對話記憶"""

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog

from src.application.agent.intent_classifier import IntentClassifier
from src.application.agent.prompt_assembler import (
    assemble as assemble_prompt,
)
from src.application.agent.prompt_assembler import (
    inject_runtime_vars,
)
from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.tool_rag_resolver import resolve_tool_rag_params
from src.domain.bot.worker_config import WorkerConfig
from src.domain.bot.worker_repository import WorkerConfigRepository
from src.domain.conversation.entity import Conversation
from src.domain.conversation.history_strategy import (
    ConversationHistoryStrategy,
    HistoryStrategyConfig,
)
from src.domain.conversation.repository import ConversationRepository
from src.domain.platform.repository import SystemPromptConfigRepository
from src.domain.platform.services import EncryptionService
from src.domain.shared.concurrency import ConversationLock
from src.domain.shared.exceptions import DomainException
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

# ── Per-tool RAG 參數組裝 ──────────────────────────────────────────
# RAG 類工具（top_k/threshold/rerank 有意義的 built-in tools）
_RAG_TOOL_NAMES: tuple[str, ...] = ("rag_query", "query_dm_with_image")


def build_tool_rag_params_map(
    *,
    bot: Bot,
    worker: WorkerConfig | None = None,
    tool_names: tuple[str, ...] = _RAG_TOOL_NAMES,
) -> dict[str, dict[str, Any]]:
    """為每個 RAG 類工具計算最終的 RAG 參數（含繼承鏈）。

    輸出 ``{tool_name: {rag_top_k, rag_score_threshold, rerank_*}}``，
    供 ReActAgentService 的 tool builder 查表使用。
    """
    return {
        name: resolve_tool_rag_params(
            tool_name=name, bot=bot, worker=worker,
        )
        for name in tool_names
    }


if TYPE_CHECKING:
    from src.application.memory.extract_memory_use_case import (
        ExtractMemoryUseCase,
    )
    from src.application.memory.load_memory_use_case import LoadMemoryUseCase
    from src.application.memory.resolve_identity_use_case import (
        ResolveIdentityUseCase,
    )
    from src.domain.tenant.repository import TenantRepository

logger = structlog.get_logger(__name__)

_REFUND_METADATA_MARKER = "__refund_metadata"


def _compute_trace_outcome(nodes: list[dict[str, Any]]) -> str:
    """S-Gov.6a: 從節點 outcome 計算 trace-level outcome。

    優先級：failed > partial > success
    """
    if any(n.get("outcome") == "failed" for n in nodes):
        return "failed"
    if any(n.get("outcome") == "partial" for n in nodes):
        return "partial"
    return "success"


def _bump_conversation_counters(conversation: Any) -> None:
    """S-Gov.6b: 寫 message 後同步更新 conversation 的 message_count
    + last_message_at（給 cron 判斷閒置 / pending summary）。

    在 conv_repo.save() 前呼叫，repo 會把這 2 欄位寫入 PG。
    """
    conversation.message_count = len(conversation.messages)
    conversation.last_message_at = datetime.now(timezone.utc)


def _build_structured_content(
    *,
    contact: dict[str, Any] | None,
    sources: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """聚合 tool 產生的 rich payload。全部為空時回傳 None，
    讓下游歷史對話可還原 contact/sources，LINE 路徑不受影響。"""
    if not contact and not sources:
        return None
    return {"contact": contact, "sources": sources}


@dataclass(frozen=True)
class SendMessageCommand:
    tenant_id: str
    kb_id: str = ""
    message: str = ""
    conversation_id: str | None = None
    bot_id: str | None = None
    visitor_id: str | None = None
    identity_source: str | None = None  # "widget" | "line"
    # Issue #54 Phase C — 影子執行（閘門驗證 / Playground）
    config_override: dict | None = None   # draft 快照 overlay（spec §13.3）
    test_mode: bool = False               # 六面隔離：不落庫、不 memory、不線上 eval
    history_override: list[dict] | None = None  # [{role, content}] 取代 DB 歷史


class SendMessageUseCase:
    def __init__(
        self,
        agent_service: AgentService,
        conversation_repository: ConversationRepository,
        bot_repository: BotRepository | None = None,
        history_strategy: ConversationHistoryStrategy | None = None,
        debug: bool = False,
        system_prompt_config_repository: SystemPromptConfigRepository | None = None,
        trace_session_factory: Any | None = None,
        mcp_registry_repo: Any | None = None,
        encryption_service: EncryptionService | None = None,
        resolve_identity_use_case: "ResolveIdentityUseCase | None" = None,
        load_memory_use_case: "LoadMemoryUseCase | None" = None,
        extract_memory_use_case: "ExtractMemoryUseCase | None" = None,
        conversation_lock: ConversationLock | None = None,
        intent_classifier: IntentClassifier | None = None,
        worker_config_repo: WorkerConfigRepository | None = None,
        prompt_guard: Any | None = None,
        tenant_repository: "TenantRepository | None" = None,
        config_version_repository: Any | None = None,
    ) -> None:
        self._agent_service = agent_service
        self._conversation_repo = conversation_repository
        self._bot_repo = bot_repository
        self._history_strategy = history_strategy
        self._debug = debug
        self._trace_session_factory = trace_session_factory
        self._sys_prompt_repo = system_prompt_config_repository
        self._mcp_registry_repo = mcp_registry_repo
        self._encryption = encryption_service
        self._resolve_identity = resolve_identity_use_case
        self._load_memory = load_memory_use_case
        self._extract_memory = extract_memory_use_case
        self._intent_classifier = intent_classifier
        self._worker_config_repo = worker_config_repo
        self._conversation_lock = conversation_lock
        self._prompt_guard = prompt_guard
        self._tenant_repo = tenant_repository
        self._config_version_repo = config_version_repository

    def _build_lock_key(self, command: SendMessageCommand) -> str:
        """Build a lock key for the conversation."""
        if command.conversation_id:
            return f"conv_lock:{command.conversation_id}"
        if command.visitor_id and command.bot_id:
            return f"conv_lock:{command.visitor_id}:{command.bot_id}"
        return ""

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
        }
        if not (command.bot_id and self._bot_repo):
            # No bot — still resolve system prompts from DB
            if self._sys_prompt_repo:
                sys_cfg = await self._sys_prompt_repo.get()
                cfg["system_prompt"] = assemble_prompt(
                    system_prompt=sys_cfg.system_prompt,
                )
            return cfg
        bot = await self._bot_repo.find_by_id(command.bot_id)
        if bot is None:
            if self._sys_prompt_repo:
                sys_cfg = await self._sys_prompt_repo.get()
                cfg["system_prompt"] = assemble_prompt(
                    system_prompt=sys_cfg.system_prompt,
                )
            return cfg
        if bot.tenant_id != command.tenant_id:
            msg = (
                f"Bot '{command.bot_id}' does not belong "
                f"to tenant '{command.tenant_id}'"
            )
            raise DomainException(msg)
        # Issue #54 Phase C — 影子執行：draft 快照 overlay 到記憶體實體。
        # 必須在租戶檢查之後（override 不得繞過隔離）、任何欄位讀取之前。
        # 紅線：影子路徑絕不可 bot_repo.save(bot)。
        if command.config_override:
            from src.domain.prompt_gate.config_snapshot import apply_snapshot
            apply_snapshot(bot, command.config_override)
        cfg["kb_ids"] = bot.knowledge_base_ids or None
        if not cfg["kb_id"] and cfg["kb_ids"]:
            cfg["kb_id"] = cfg["kb_ids"][0]
        cfg["system_prompt"] = bot.bot_prompt or None
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
        cfg["customer_service_url"] = bot.customer_service_url
        # Stash bot entity + initial per-tool params (worker routing may override)
        cfg["_bot"] = bot
        cfg["tool_rag_params"] = build_tool_rag_params_map(bot=bot)
        cfg["mcp_servers"] = [
            {
                "url": s.url,
                "name": s.name,
                "enabled_tools": s.enabled_tools,
                "transport": s.transport,
                **({"command": s.command, "args": s.args} if s.transport == "stdio" else {}),
            }
            for s in bot.mcp_servers
        ]

        # Registry-based MCP bindings → resolved server configs
        if bot.mcp_bindings and self._mcp_registry_repo:
            registry_servers: list[dict[str, Any]] = []
            for binding in bot.mcp_bindings:
                reg = await self._mcp_registry_repo.find_by_id(
                    binding.registry_id
                )
                if not reg or not reg.is_enabled:
                    continue
                # Tenant scope check: skip if not accessible
                if (
                    reg.scope == "tenant"
                    and command.tenant_id not in reg.tenant_ids
                ):
                    continue

                # Decrypt env_values (stored encrypted in DB)
                decrypted_env: dict[str, str] = {}
                for k, v in binding.env_values.items():
                    if not v:
                        decrypted_env[k] = ""
                    elif self._encryption:
                        try:
                            decrypted_env[k] = self._encryption.decrypt(v)
                        except Exception:
                            # Fallback: pre-migration plaintext data
                            decrypted_env[k] = v
                    else:
                        decrypted_env[k] = v

                server_cfg: dict[str, Any] = {
                    "name": reg.name,
                    "transport": reg.transport,
                }
                if reg.transport == "stdio":
                    server_cfg["command"] = reg.command
                    server_cfg["args"] = reg.args
                    server_cfg["env"] = decrypted_env
                else:
                    resolved_url = reg.url
                    for key, value in decrypted_env.items():
                        resolved_url = resolved_url.replace(
                            f"{{{key}}}", value
                        )
                    server_cfg["url"] = resolved_url
                if binding.enabled_tools:
                    server_cfg["enabled_tools"] = binding.enabled_tools
                registry_servers.append(server_cfg)
            if registry_servers:
                cfg["mcp_servers"] = registry_servers

        cfg["max_tool_calls"] = bot.max_tool_calls or 5
        cfg["bot_id"] = bot.id.value
        cfg["memory_enabled"] = getattr(bot, "memory_enabled", False)
        cfg["memory_extraction_threshold"] = getattr(
            bot, "memory_extraction_threshold", 3
        )
        cfg["memory_extraction_prompt"] = getattr(
            bot, "memory_extraction_prompt", ""
        )
        cfg["rerank_enabled"] = getattr(bot, "rerank_enabled", False)
        cfg["rerank_model"] = getattr(bot, "rerank_model", "")
        cfg["rerank_top_n"] = getattr(bot, "rerank_top_n", 20)
        # Issue #43 — Bot-level RAG retrieval modes
        cfg["rag_retrieval_modes"] = list(
            getattr(bot, "rag_retrieval_modes", ["raw"]) or ["raw"]
        )
        cfg["query_rewrite_enabled"] = getattr(
            bot, "query_rewrite_enabled", False
        )
        cfg["query_rewrite_model"] = getattr(bot, "query_rewrite_model", "")
        cfg["query_rewrite_extra_hint"] = getattr(
            bot, "query_rewrite_extra_hint", ""
        )
        cfg["hyde_enabled"] = getattr(bot, "hyde_enabled", False)
        cfg["hyde_model"] = getattr(bot, "hyde_model", "")
        cfg["hyde_extra_hint"] = getattr(bot, "hyde_extra_hint", "")
        cfg["bot_prompt"] = bot.bot_prompt or ""
        cfg["eval_depth"] = getattr(bot, "eval_depth", "off")
        cfg["eval_provider"] = getattr(bot, "eval_provider", "")
        cfg["eval_model"] = getattr(bot, "eval_model", "")
        cfg["intent_routes"] = list(getattr(bot, "intent_routes", []))
        # S-KB-Followup.2: bot-level model 空 → fallback tenant default → 空 → 系統 default
        _bot_router_model = getattr(bot, "router_model", "")
        _bot_summary_model = getattr(bot, "summary_model", "")
        _tenant_default_intent = ""
        _tenant_default_summary = ""
        if (not _bot_router_model or not _bot_summary_model) and self._tenant_repo:
            try:
                _tenant = await self._tenant_repo.find_by_id(command.tenant_id)
                if _tenant is not None:
                    _tenant_default_intent = getattr(_tenant, "default_intent_model", "")
                    _tenant_default_summary = getattr(_tenant, "default_summary_model", "")
            except Exception:
                pass
        cfg["router_model"] = _bot_router_model or _tenant_default_intent
        cfg["summary_model"] = _bot_summary_model or _tenant_default_summary

        # Resolve prompt overrides: Bot → SystemPromptConfig → Seed
        resolved_system_prompt = ""
        if self._sys_prompt_repo:
            sys_cfg = await self._sys_prompt_repo.get()
            resolved_system_prompt = bot.base_prompt or sys_cfg.system_prompt

        # Pre-assemble the full system prompt (agent services use it directly)
        cfg["system_prompt"] = assemble_prompt(
            bot_prompt=bot.bot_prompt,
            system_prompt=resolved_system_prompt,
        )

        return cfg

    async def _resolve_and_load_memory(
        self, command: SendMessageCommand, bot_cfg: dict[str, Any]
    ) -> str:
        """Resolve visitor identity and load memory context.

        Returns formatted memory prompt string (empty if disabled).
        """
        if not command.visitor_id or not command.identity_source:
            return ""
        if not bot_cfg.get("memory_enabled", False):
            return ""
        if not self._resolve_identity or not self._load_memory:
            return ""

        try:
            from src.application.memory.load_memory_use_case import (
                LoadMemoryCommand,
            )
            from src.application.memory.resolve_identity_use_case import (
                ResolveIdentityCommand,
            )

            profile_id = await self._resolve_identity.execute(
                ResolveIdentityCommand(
                    tenant_id=command.tenant_id,
                    source=command.identity_source,
                    external_id=command.visitor_id,
                )
            )
            memory_ctx = await self._load_memory.execute(
                LoadMemoryCommand(profile_id=profile_id)
            )
            if memory_ctx.has_memory:
                return memory_ctx.formatted_prompt
        except Exception:
            logger.warning("memory.load_failed", exc_info=True)
        return ""

    def _should_extract_memory(
        self, bot_cfg: dict[str, Any], message_count: int
    ) -> bool:
        """Check if memory extraction should be triggered."""
        if not bot_cfg.get("memory_enabled", False):
            return False
        threshold = bot_cfg.get("memory_extraction_threshold", 3)
        if message_count < threshold * 2:
            return False
        return True

    async def _fire_memory_extraction(
        self,
        command: SendMessageCommand,
        bot_cfg: dict[str, Any],
        conversation: Conversation,
    ) -> None:
        """Fire-and-forget memory extraction (background task)."""
        if not command.visitor_id or not command.identity_source:
            return
        if not self._resolve_identity or not self._extract_memory:
            return
        if not self._should_extract_memory(bot_cfg, len(conversation.messages)):
            return

        try:
            from src.application.memory.resolve_identity_use_case import (
                ResolveIdentityCommand,
            )

            profile_id = await self._resolve_identity.execute(
                ResolveIdentityCommand(
                    tenant_id=command.tenant_id,
                    source=command.identity_source,
                    external_id=command.visitor_id,
                )
            )

            # Only pass the latest user+assistant pair for extraction
            recent_messages = []
            for msg in conversation.messages[-2:]:
                recent_messages.append(
                    {"role": msg.role, "content": msg.content}
                )

            from src.infrastructure.queue.arq_pool import enqueue
            await enqueue(
                "extract_memory",
                profile_id,
                command.tenant_id,
                conversation.id.value,
                recent_messages,
                bot_cfg.get("memory_extraction_prompt", ""),
            )
        except Exception:
            logger.warning("memory.extraction_dispatch_failed", exc_info=True)

    async def _resolve_history(
        self,
        history: list | None,
        history_limit: int | None,
        tenant_id: str = "",
    ) -> tuple[list | None, str, str]:
        """Process history via strategy, return (history, ctx, router).

        Defensive：若 strategy 對非空 history 仍輸出空 context，或 strategy
        未注入，都用 _format_messages 直接 fallback。確保「歷史輪數 > 0
        但歷史上下文 = 空」的詭異案例不再發生。
        """
        history_context = ""
        router_context = ""
        t_hist = AgentTraceCollector.offset_ms()
        if self._history_strategy and history:
            strategy_config = HistoryStrategyConfig(
                history_limit=history_limit or 10,
                recent_turns=3,
                tenant_id=tenant_id,
            )
            ctx = await self._history_strategy.process(
                history, strategy_config
            )
            history_context = ctx.respond_context
            router_context = ctx.router_context
            # Defensive：策略對非空 history 卻吐空字串（regression 警示）
            if history and not history_context:
                from src.infrastructure.conversation.sliding_window_strategy import (
                    _format_messages,
                )
                history_context = _format_messages(
                    history[-(history_limit or 10) :]
                )
                logger.warning(
                    "history.strategy_empty_fallback",
                    strategy=self._history_strategy.name,
                    history_len=len(history),
                    fallback_chars=len(history_context),
                )
        elif history and history_limit is not None:
            # 沒注入 strategy（理論不應發生，但要 graceful）
            history = history[-history_limit:]
            from src.infrastructure.conversation.sliding_window_strategy import (
                _format_messages,
            )
            history_context = _format_messages(history)
            logger.warning(
                "history.no_strategy_fallback",
                history_len=len(history),
            )
        if history:
            AgentTraceCollector.span(
                "history_load", "歷史載入", t_hist,
                message_count=len(history),
                strategy=(
                    getattr(self._history_strategy, "name", "")
                    if self._history_strategy else "fallback"
                ),
            )
        return history, history_context, router_context

    async def _get_busy_reply_message(self, command: SendMessageCommand) -> str:
        """Load bot's busy_reply_message for lock rejection."""
        if command.bot_id and self._bot_repo:
            bot = await self._bot_repo.find_by_id(command.bot_id)
            if bot:
                return bot.busy_reply_message
        return "小編正在努力回覆中，請稍等一下喔～"

    async def _resolve_worker_config(
        self,
        bot_cfg: dict[str, Any],
        message: str,
        router_context: str,
        tenant_id: str = "",
        test_mode: bool = False,
    ) -> dict[str, Any]:
        """Worker routing: classify → override bot_cfg with worker settings.

        Returns bot_cfg unchanged if no workers or no match.
        """
        if not self._worker_config_repo or not self._intent_classifier:
            return bot_cfg
        bot_id = bot_cfg.get("bot_id", "")
        if not bot_id:
            return bot_cfg

        workers = await self._worker_config_repo.find_by_bot_id(
            bot_id
        )
        if not workers:
            # No workers configured — also try legacy intent_routes
            intent_routes = bot_cfg.get("intent_routes", [])
            if intent_routes:
                # Token-Gov.7 A: 包 trace node 記錄 intent classifier LLM 時間
                t_start = AgentTraceCollector.offset_ms()
                matched = await self._intent_classifier.classify(
                    user_message=message,
                    router_context=router_context,
                    intent_routes=intent_routes,
                    tenant_id=tenant_id,
                    bot_id=bot_id,
                    test_mode=test_mode,  # M14：影子執行不記生產 token
                )
                t_end = AgentTraceCollector.offset_ms()
                AgentTraceCollector.add_node(
                    node_type="intent_classify",
                    label=(
                        f"意圖分類 → {matched.name}" if matched
                        else "意圖分類 → 預設 fallback"
                    ),
                    parent_id=None,
                    start_ms=t_start,
                    end_ms=t_end,
                    matched=matched.name if matched else None,
                    candidates=[r.name for r in intent_routes],
                )
                if matched:
                    bot_cfg["system_prompt"] = inject_runtime_vars(
                        matched.system_prompt
                    )
            return bot_cfg

        # Token-Gov.7 A: 包 trace node 記錄 intent classifier LLM 時間
        t_start = AgentTraceCollector.offset_ms()
        # H11：改用 classify_sanitize（與 LINE 同）以取得 is_attack。2026-08-17 起
        # regex guard 已不做語意判斷，語意型攻擊（同義改寫/拆字/多輪鋪陳）的唯一防線
        # 是分類器的攻擊判定——原本 web/widget 用 classify_workers 把 is_attack 丟棄，
        # 導致此防護只在 LINE 生效、web/widget（含匿名 public widget 端點）裸奔。
        outcome = await self._intent_classifier.classify_sanitize(
            user_message=message,
            router_context=router_context,
            workers=workers,
            router_model=bot_cfg.get("router_model", ""),
            tenant_id=tenant_id,
            bot_id=bot_id,
            test_mode=test_mode,  # M14：影子執行不記生產 token
        )
        matched = outcome.worker
        bot_cfg["_classifier_attack"] = outcome.is_attack
        t_end = AgentTraceCollector.offset_ms()
        AgentTraceCollector.add_node(
            node_type="intent_classify",
            label=(
                f"意圖分類 → {matched.name}" if matched
                else "意圖分類 → 預設 fallback"
            ),
            parent_id=None,
            start_ms=t_start,
            end_ms=t_end,
            matched=matched.name if matched else None,
            candidates=[w.name for w in workers],
            classifier_model=bot_cfg.get("router_model", ""),
        )
        if not matched:
            return bot_cfg

        # Override bot_cfg with worker settings
        cfg = {**bot_cfg}
        if matched.worker_prompt:
            cfg["system_prompt"] = inject_runtime_vars(
                matched.worker_prompt
            )
        # M17：temperature/max_tokens 賦值原本在 provider/model 條件內 → worker 沿用
        # bot 模型（不指定 provider/model）時 web 忽略 worker 的取樣參數，但 LINE 無條件
        # 套用 → 同一 worker 兩通路取樣參數/回覆長度不同。移出條件，與 LINE 對齊。
        cfg["llm_params"] = {
            **(cfg.get("llm_params") or {}),
            **(
                {"provider_name": matched.llm_provider}
                if matched.llm_provider
                else {}
            ),
            **(
                {"model": matched.llm_model}
                if matched.llm_model
                else {}
            ),
            "temperature": matched.temperature,
            "max_tokens": matched.max_tokens,
        }
        cfg["max_tool_calls"] = matched.max_tool_calls

        # Filter MCP servers to worker's subset
        if matched.enabled_mcp_ids:
            all_servers = cfg.get("mcp_servers") or []
            cfg["mcp_servers"] = [
                s
                for s in all_servers
                if s.get("name") in matched.enabled_mcp_ids
                or s.get("registry_id") in matched.enabled_mcp_ids
            ]

        # Knowledge base override
        if matched.knowledge_base_ids:
            cfg["kb_ids"] = matched.knowledge_base_ids
            cfg["kb_id"] = matched.knowledge_base_ids[0]
        # Enabled tools override（None = 繼承 Bot；list 即使為空也是顯式覆蓋）
        if matched.enabled_tools is not None:
            cfg["enabled_tools"] = list(matched.enabled_tools)
        # If empty list explicitly set → no RAG
        # (default from bot if not configured on worker)

        # Per-tool RAG 參數：Worker per-tool → Bot per-tool → Bot 全域
        bot_entity = cfg.get("_bot")
        if bot_entity is not None:
            cfg["tool_rag_params"] = build_tool_rag_params_map(
                bot=bot_entity, worker=matched,
            )

        # Stash for agent trace node（process_message 會讀並加到 AgentTraceCollector）
        cfg["_worker_matched_info"] = {
            "name": matched.name,
            "llm_model": matched.llm_model or "",
            "llm_provider": matched.llm_provider or "",
            "kb_count": len(matched.knowledge_base_ids),
        }

        logger.info(
            "worker_routing.matched",
            worker_name=matched.name,
            llm_model=matched.llm_model,
            tool_count=len(cfg.get("mcp_servers") or []),
            kb_count=len(matched.knowledge_base_ids),
        )
        return cfg

    async def execute(self, command: SendMessageCommand) -> AgentResponse:
        # Acquire conversation lock
        lock_key = self._build_lock_key(command)
        if lock_key and self._conversation_lock:
            async with self._conversation_lock.acquire(lock_key) as acquired:
                if not acquired:
                    busy_msg = await self._get_busy_reply_message(command)
                    return AgentResponse(answer=busy_msg)
                return await self._execute_inner(command)
        return await self._execute_inner(command)

    async def _execute_inner(self, command: SendMessageCommand) -> AgentResponse:
        # Issue #57：trace 從 use case 進入點起算（請求邊界），前置的對話載入 /
        # bot 設定載入各成節點；start 為 idempotent，後面的 start 只補欄位。
        AgentTraceCollector.start(
            tenant_id=command.tenant_id, agent_mode="", bot_id=command.bot_id,
        )
        t_conv = AgentTraceCollector.offset_ms()
        conversation = await self._load_or_create_conversation(command)
        AgentTraceCollector.span("conversation_load", "對話載入", t_conv)

        history = conversation.messages if conversation.messages else None
        metadata = self._extract_metadata(conversation)
        metadata["_dry_run_guard"] = command.test_mode  # H6

        t_bot = AgentTraceCollector.offset_ms()
        bot_cfg = await self._load_bot_config(command)
        AgentTraceCollector.span("bot_load", "Bot 設定載入", t_bot)

        # Inject rerank config into metadata for RAG tool
        metadata["rerank_enabled"] = bot_cfg.get("rerank_enabled", False)
        metadata["rerank_model"] = bot_cfg.get("rerank_model", "")
        metadata["rerank_top_n"] = bot_cfg.get("rerank_top_n", 20)
        # Issue #43 — Bot-level RAG retrieval modes
        metadata["rag_retrieval_modes"] = list(
            bot_cfg.get("rag_retrieval_modes", ["raw"]) or ["raw"]
        )
        metadata["query_rewrite_model"] = bot_cfg.get("query_rewrite_model", "")
        metadata["query_rewrite_extra_hint"] = bot_cfg.get(
            "query_rewrite_extra_hint", ""
        )
        metadata["hyde_model"] = bot_cfg.get("hyde_model", "")
        metadata["hyde_extra_hint"] = bot_cfg.get("hyde_extra_hint", "")
        metadata["bot_prompt"] = bot_cfg.get("bot_prompt", "")

        # 提早 start AgentTraceCollector — guard 命中時要 add_node，否則
        # 在 agent_service.start() 之前 add_node 會被 trace=None 吞掉
        # → DAG 永遠看不到 guard_input_blocked 紅節點。
        # AgentTraceCollector.start 是 idempotent，agent_service 後面再 call
        # 不會重置已建立的 trace。
        AgentTraceCollector.start(
            tenant_id=command.tenant_id,
            agent_mode="",  # agent_service 後續會補
            conversation_id=conversation.id.value,
            bot_id=command.bot_id,
        )

        # ── Prompt Guard: input check (must be FIRST LLM-affecting gate) ──
        # 之前擺在 _resolve_worker_config 之後，但 worker routing 的 intent
        # classifier 已經把 user_message 餵給 LLM → prompt injection 已經
        # compromise 那層 LLM。提前到任何 LLM-touching helper 之前。
        blocked = await self._check_input_guard(
            command, conversation, metadata
        )
        if blocked is not None:
            return blocked

        history, history_context, router_context = (
            await self._resolve_history(
                history, bot_cfg["history_limit"], tenant_id=command.tenant_id
            )
        )

        # Memory: resolve identity + load
        memory_prompt = await self._resolve_and_load_memory(command, bot_cfg)
        if memory_prompt:
            history_context = (
                memory_prompt + "\n\n" + history_context
                if history_context
                else memory_prompt
            )

        # Worker routing: classify → override bot_cfg
        bot_cfg = await self._resolve_worker_config(
            bot_cfg, command.message, router_context,
            tenant_id=command.tenant_id,
            test_mode=command.test_mode,  # M14：影子執行不記生產分類 token
        )

        # H11：分類器語意攻擊短路（與 LINE 對等）——攻擊句不進生成模型
        attack_block = await self._check_classifier_attack(
            command, conversation, bot_cfg
        )
        if attack_block is not None:
            return attack_block

        # Propagate worker routing info to agent service (for trace visualization)
        if bot_cfg.get("_worker_matched_info"):
            metadata["_worker_routing"] = bot_cfg["_worker_matched_info"]

        t0 = time.perf_counter()
        response = await self._agent_service.process_message(
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
            tool_rag_params=bot_cfg.get("tool_rag_params"),
            customer_service_url=bot_cfg.get("customer_service_url", ""),
            mcp_servers=bot_cfg.get("mcp_servers"),
            max_tool_calls=bot_cfg.get("max_tool_calls", 5),
            bot_id=bot_cfg.get("bot_id", ""),
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)

        retrieved_chunks = (
            [s.to_dict() for s in response.sources]
            if response.sources
            else None
        )
        structured_content = _build_structured_content(
            contact=response.contact,
            sources=retrieved_chunks,
        )

        tool_calls_to_save = response.tool_calls[:]
        if response.refund_step:
            tool_calls_to_save.append(
                {
                    "tool_name": _REFUND_METADATA_MARKER,
                    "refund_step": response.refund_step,
                }
            )

        # ── Prompt Guard: output check ──
        if self._prompt_guard:
            guard_result = await self._prompt_guard.check_output(
                response.answer,
                tenant_id=command.tenant_id,
                bot_id=command.bot_id,
                user_id=command.visitor_id,
                user_message=command.message,
                dry_run=command.test_mode,  # H6
            )
            if not guard_result.passed:
                response.answer = guard_result.blocked_response
                # Sprint A++ Guard UX
                response.guard_blocked = "output"
                response.guard_rule_matched = guard_result.rule_matched

        assistant_msg = None
        t_persist = AgentTraceCollector.offset_ms()
        if not command.test_mode:
            conversation.add_message("user", command.message)
            assistant_msg = conversation.add_message(
                "assistant",
                response.answer,
                tool_calls=tool_calls_to_save,
                latency_ms=latency_ms,
                retrieved_chunks=retrieved_chunks,
                structured_content=structured_content,
            )
            _bump_conversation_counters(conversation)
            await self._conversation_repo.save(conversation)

        response.conversation_id = conversation.id.value
        # S-ConvInsights.1: 暴露 assistant message_id 給 agent_router 用於 RecordUsage
        response.message_id = (
            assistant_msg.id.value if assistant_msg else None
        )

        # Fire-and-forget: persist agent execution trace
        # （修既有債：非 stream 路徑補傳 message_id，spec §7.3 C-3）
        trace_id, trace_nodes = await self._persist_agent_trace(
            conversation_id=conversation.id.value,
            message_id=response.message_id,
            latency_ms=latency_ms,
            source=command.identity_source or "web",
            persist_started_ms=t_persist,
            persist=not command.test_mode,
        )
        if command.test_mode:
            response.trace_id = trace_id
            response.trace_nodes = trace_nodes
            return response  # 六面隔離：不 memory、不線上 eval

        # Issue #54 §13.6 — usage 打標：生成當下的線上設定版本
        response.config_version_id = await self._resolve_current_version_id(
            command.bot_id
        )

        # Fire-and-forget: memory extraction
        await self._fire_memory_extraction(command, bot_cfg, conversation)

        # Issue #59：線上每輪 LLM 自評已下線（品質驗收走 prompt gate 離線回放）

        return response

    async def execute_stream(
        self, command: SendMessageCommand
    ) -> AsyncIterator[dict[str, Any]]:
        # Acquire conversation lock
        lock_key = self._build_lock_key(command)
        if lock_key and self._conversation_lock:
            async with self._conversation_lock.acquire(lock_key) as acquired:
                if not acquired:
                    busy_msg = await self._get_busy_reply_message(command)
                    yield {"type": "token", "content": busy_msg}
                    yield {"type": "done"}
                    return
                async for event in self._execute_stream_inner(command):
                    yield event
                return
        async for event in self._execute_stream_inner(command):
            yield event

    async def _execute_stream_inner(
        self, command: SendMessageCommand
    ) -> AsyncIterator[dict[str, Any]]:
        # Issue #57：trace 從 use case 進入點起算（請求邊界），前置的對話載入 /
        # bot 設定載入各成節點；start 為 idempotent，後面的 start 只補欄位。
        AgentTraceCollector.start(
            tenant_id=command.tenant_id, agent_mode="", bot_id=command.bot_id,
        )
        t_conv = AgentTraceCollector.offset_ms()
        conversation = await self._load_or_create_conversation(command)
        AgentTraceCollector.span("conversation_load", "對話載入", t_conv)

        history = conversation.messages if conversation.messages else None
        metadata = self._extract_metadata(conversation)
        metadata["_dry_run_guard"] = command.test_mode  # H6

        t_bot = AgentTraceCollector.offset_ms()
        bot_cfg = await self._load_bot_config(command)
        AgentTraceCollector.span("bot_load", "Bot 設定載入", t_bot)

        # Inject rerank config into metadata for RAG tool
        metadata["rerank_enabled"] = bot_cfg.get("rerank_enabled", False)
        metadata["rerank_model"] = bot_cfg.get("rerank_model", "")
        metadata["rerank_top_n"] = bot_cfg.get("rerank_top_n", 20)
        # Issue #43 — Bot-level RAG retrieval modes
        metadata["rag_retrieval_modes"] = list(
            bot_cfg.get("rag_retrieval_modes", ["raw"]) or ["raw"]
        )
        metadata["query_rewrite_model"] = bot_cfg.get("query_rewrite_model", "")
        metadata["query_rewrite_extra_hint"] = bot_cfg.get(
            "query_rewrite_extra_hint", ""
        )
        metadata["hyde_model"] = bot_cfg.get("hyde_model", "")
        metadata["hyde_extra_hint"] = bot_cfg.get("hyde_extra_hint", "")
        metadata["bot_prompt"] = bot_cfg.get("bot_prompt", "")

        # 提早 start AgentTraceCollector — guard 命中時要 add_node，否則
        # 在 agent_service.start() 之前 add_node 會被 trace=None 吞掉
        # → DAG 永遠看不到 guard_input_blocked 紅節點。
        AgentTraceCollector.start(
            tenant_id=command.tenant_id,
            agent_mode="",  # agent_service 後續會補
            conversation_id=conversation.id.value,
            bot_id=command.bot_id,
        )

        # ── Prompt Guard: input check (must be FIRST LLM-affecting gate) ──
        # 之前擺在 _resolve_worker_config 之後，但 worker routing 的 intent
        # classifier 已經把 user_message 餵給 LLM → prompt injection 已經
        # compromise 那層 LLM。提前到任何 LLM-touching helper 之前。
        if self._prompt_guard:
            guard_result = await self._prompt_guard.check_input(
                command.message,
                tenant_id=command.tenant_id,
                bot_id=command.bot_id,
                user_id=command.visitor_id,
                dry_run=command.test_mode,  # H6
            )
            if not guard_result.passed:
                assistant_msg = None
                if not command.test_mode:
                    conversation.add_message("user", command.message)
                    assistant_msg = conversation.add_message(
                        "assistant", guard_result.blocked_response
                    )
                    _bump_conversation_counters(conversation)
                    await self._conversation_repo.save(conversation)
                yield {
                    "type": "token",
                    "content": guard_result.blocked_response,
                }
                yield {
                    "type": "guard_blocked",
                    "block_type": "input",
                    "rule_matched": guard_result.rule_matched,
                }
                # 持久化 trace（含 guard_input_blocked 紅節點），讓 Studio
                # canvas / admin 觀測頁能看到攔截 DAG
                gb_trace_id, gb_nodes = await self._persist_agent_trace(
                    conversation_id=conversation.id.value,
                    message_id=(
                        assistant_msg.id.value if assistant_msg else None
                    ),
                    latency_ms=0,
                    source=command.identity_source or "web",
                    persist=not command.test_mode,
                )
                # M10：原本丟棄回傳的 (trace_id, nodes)、done 不帶 → 前端拿不到
                # trace_id 無法 fetch 剛持久化的 guard DAG；test_mode 下 trace 不落庫、
                # 資訊全失。比照正常結束路徑帶上。
                gb_done: dict[str, Any] = {"type": "done"}
                if gb_trace_id:
                    gb_done["trace_id"] = gb_trace_id
                if command.test_mode and gb_nodes:
                    gb_done["trace_nodes"] = gb_nodes
                yield gb_done
                return

        history, history_context, router_context = (
            await self._resolve_history(
                history, bot_cfg["history_limit"], tenant_id=command.tenant_id
            )
        )

        # Memory: resolve identity + load
        memory_prompt = await self._resolve_and_load_memory(command, bot_cfg)
        if memory_prompt:
            history_context = (
                memory_prompt + "\n\n" + history_context
                if history_context
                else memory_prompt
            )

        # Worker routing: classify → override bot_cfg
        bot_cfg = await self._resolve_worker_config(
            bot_cfg, command.message, router_context,
            tenant_id=command.tenant_id,
            test_mode=command.test_mode,  # M14：影子執行不記生產分類 token
        )

        # H11：分類器語意攻擊短路（與 LINE 對等）——攻擊句不進生成模型。
        # widget 端由 router 過濾 guard_blocked 事件（H7），只收到固定文案。
        if bot_cfg.get("_classifier_attack") and self._prompt_guard:
            gr = await self._prompt_guard.block_by_classifier(
                message=command.message,
                tenant_id=command.tenant_id,
                bot_id=command.bot_id,
                user_id=command.visitor_id,
                dry_run=command.test_mode,  # H6
            )
            attack_msg = None
            if not command.test_mode:
                conversation.add_message("user", command.message)
                attack_msg = conversation.add_message(
                    "assistant", gr.blocked_response
                )
                _bump_conversation_counters(conversation)
                await self._conversation_repo.save(conversation)
            yield {"type": "token", "content": gr.blocked_response}
            yield {
                "type": "guard_blocked",
                "block_type": "input",
                "rule_matched": gr.rule_matched,
            }
            atk_trace_id, atk_nodes = await self._persist_agent_trace(
                conversation_id=conversation.id.value,
                message_id=attack_msg.id.value if attack_msg else None,
                latency_ms=0,
                source=command.identity_source or "web",
                persist=not command.test_mode,
            )
            atk_done: dict[str, Any] = {"type": "done"}  # M10
            if atk_trace_id:
                atk_done["trace_id"] = atk_trace_id
            if command.test_mode and atk_nodes:
                atk_done["trace_nodes"] = atk_nodes
            yield atk_done
            return

        # Propagate worker routing info to agent service (for trace visualization)
        if bot_cfg.get("_worker_matched_info"):
            metadata["_worker_routing"] = bot_cfg["_worker_matched_info"]

        # Stream from agent service
        full_answer = ""
        tool_calls: list[dict[str, Any]] = []
        sources_list: list[dict[str, Any]] = []
        contact_payload: dict[str, Any] | None = None
        refund_step_value: str | None = None

        t0 = time.perf_counter()
        async for event in self._agent_service.process_message_stream(
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
            tool_rag_params=bot_cfg.get("tool_rag_params"),
            customer_service_url=bot_cfg.get("customer_service_url", ""),
            mcp_servers=bot_cfg.get("mcp_servers"),
            max_tool_calls=bot_cfg.get("max_tool_calls", 5),
            bot_id=bot_cfg.get("bot_id", ""),
        ):
            # contact event 不塞進 answer，透過 yield 傳給呼叫者
            if event["type"] == "token":
                full_answer += event["content"]
            elif event["type"] == "tool_calls":
                tool_calls = event.get("tool_calls", [])
            elif event["type"] == "sources":
                sources_list = event.get("sources", [])
            elif event["type"] == "contact":
                contact_payload = event.get("contact")
            elif event["type"] == "refund_step":
                refund_step_value = event.get("refund_step")
                continue  # Internal metadata, not sent to client
            # Non-debug: hide "direct" tool_calls entirely, strip reasoning for others
            if event["type"] == "tool_calls" and not self._debug:
                tcs = event.get("tool_calls", [])
                # "direct" means no tool used — nothing to show
                if all(tc.get("tool_name") == "direct" for tc in tcs):
                    continue
                event = {
                    "type": "tool_calls",
                    "tool_calls": [
                        {
                            "tool_name": tc.get("tool_name", ""),
                            "label": tc.get("label", ""),
                            "reasoning": "",
                        }
                        for tc in tcs
                    ],
                }
            # Suppress sources event when bot has show_sources=False
            if event["type"] == "sources" and not bot_cfg["show_sources"]:
                continue
            yield event
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # ── Prompt Guard: output check on accumulated answer (Option B) ──
        # 串流結束後檢查整段 full_answer，命中時：
        # - DB 存乾淨版（blocked_response 取代原文）
        # - emit guard_blocked 事件給 Studio 前端，前端覆寫對話泡泡
        # - 端使用者(widget/LINE)透過 router sanitize 拿不到此事件，
        #   即時看到原文無法擋（keyword-based guard 的天花板，已記在 docs）
        if self._prompt_guard and full_answer:
            output_guard = await self._prompt_guard.check_output(
                full_answer,
                tenant_id=command.tenant_id,
                bot_id=command.bot_id,
                user_id=command.visitor_id,
                user_message=command.message,
                dry_run=command.test_mode,  # H6
            )
            if not output_guard.passed:
                full_answer = output_guard.blocked_response
                yield {
                    "type": "guard_blocked",
                    "block_type": "output",
                    "rule_matched": output_guard.rule_matched,
                    "replacement": full_answer,
                }

        retrieved_chunks = sources_list if sources_list else None
        structured_content = _build_structured_content(
            contact=contact_payload,
            sources=retrieved_chunks,
        )

        # Save conversation after streaming completes
        # Persist refund_step metadata marker (same logic as execute())
        tool_calls_to_save = tool_calls[:]
        if refund_step_value:
            tool_calls_to_save.append({
                "tool_name": _REFUND_METADATA_MARKER,
                "refund_step": refund_step_value,
            })

        assistant_msg = None
        t_persist = AgentTraceCollector.offset_ms()
        if not command.test_mode:
            conversation.add_message("user", command.message)
            assistant_msg = conversation.add_message(
                "assistant",
                full_answer,
                tool_calls=tool_calls_to_save,
                latency_ms=latency_ms,
                retrieved_chunks=retrieved_chunks,
                structured_content=structured_content,
            )
            _bump_conversation_counters(conversation)
            await self._conversation_repo.save(conversation)

        # 在 _persist_agent_trace 之前取 trace_id（finish 後 ContextVar 會被清掉）
        # 用於 SSE done 事件回傳給前端，讓 Studio canvas 等可 fetch 完整 DAG。
        _current_trace = AgentTraceCollector.current()
        stream_trace_id = _current_trace.trace_id if _current_trace else None

        # Fire-and-forget: persist agent execution trace
        _, stream_trace_nodes = await self._persist_agent_trace(
            conversation_id=conversation.id.value,
            message_id=(
                assistant_msg.id.value if assistant_msg else None
            ),
            latency_ms=latency_ms,
            source=command.identity_source or "web",
            persist=not command.test_mode,
            persist_started_ms=t_persist,
        )

        if not command.test_mode:
            # Fire-and-forget: memory extraction（test_mode 六面隔離跳過）
            await self._fire_memory_extraction(command, bot_cfg, conversation)

        # Issue #59：線上每輪 LLM 自評已下線（品質驗收走 prompt gate 離線回放）

        if assistant_msg is not None:
            yield {
                "type": "message_id",
                "message_id": assistant_msg.id.value,
            }
            cv_id = await self._resolve_current_version_id(command.bot_id)
            if cv_id:
                yield {
                    "type": "config_version",
                    "config_version_id": cv_id,
                }
        yield {
            "type": "conversation_id",
            "conversation_id": conversation.id.value,
        }
        done_event: dict[str, Any] = {"type": "done"}
        if stream_trace_id:
            done_event["trace_id"] = stream_trace_id
        if command.test_mode and stream_trace_nodes is not None:
            done_event["trace_nodes"] = stream_trace_nodes
        yield done_event

    async def _load_or_create_conversation(
        self, command: SendMessageCommand
    ) -> Conversation:
        # Issue #54 Phase C — test_mode：不讀不寫 DB，一律新建記憶體對話；
        # history_override 直接灌成訊息（多輪題/Playground 的歷史來源）
        if command.test_mode:
            conv = Conversation(
                tenant_id=command.tenant_id, bot_id=command.bot_id
            )
            for m in command.history_override or []:
                conv.add_message(
                    str(m.get("role", "user")), str(m.get("content", ""))
                )
            return conv
        if command.conversation_id:
            existing = await self._conversation_repo.find_by_id(
                command.conversation_id
            )
            # 歸屬檢查（C2）：conversation_id 未帶歸屬，find_by_id 不做 tenant
            # 過濾。不比對會讓任一租戶帶他人 conversation_id 讀到對方歷史、
            # 並把訊息寫進對方對話。不屬於此租戶/bot（或不存在）→ 不沿用外來
            # id，改開新對話。
            if (
                existing is not None
                and existing.tenant_id == command.tenant_id
                and existing.bot_id == command.bot_id
            ):
                return existing

        return Conversation(tenant_id=command.tenant_id, bot_id=command.bot_id)

    async def _check_input_guard(
        self, command: SendMessageCommand, conversation, metadata: dict
    ) -> AgentResponse | None:
        """Input guard 前置檢查；攔截時回傳攔截回應（test_mode 不落庫）。"""
        if not self._prompt_guard:
            return None
        guard_result = await self._prompt_guard.check_input(
            command.message,
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            user_id=command.visitor_id,
            dry_run=command.test_mode,  # H6
        )
        if guard_result.passed:
            # F1（POC 問題 1）：input guard 已在此跑過並通過 — 帶標記讓
            # GuardedAgentService 咽喉點跳過重複的 input guard LLM roundtrip
            metadata["_input_guard_checked"] = True
            return None
        return await self._finalize_input_block(
            command, conversation, guard_result
        )

    async def _check_classifier_attack(
        self, command: SendMessageCommand, conversation, bot_cfg: dict
    ) -> AgentResponse | None:
        """H11：分類器判純攻擊 → 與 regex guard 同一份固定文案短路（web/widget）。

        worker routing 的 classify_sanitize 在 _resolve_worker_config 已把 is_attack
        暫存於 bot_cfg；此處走 block_by_classifier（與 LINE block_by_classifier 同副作用
        與文案）並回傳攔截回應。無 workers / 非攻擊 / 無 guard → None。
        """
        if not bot_cfg.get("_classifier_attack") or not self._prompt_guard:
            return None
        guard_result = await self._prompt_guard.block_by_classifier(
            message=command.message,
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            user_id=command.visitor_id,
            dry_run=command.test_mode,  # H6
        )
        return await self._finalize_input_block(
            command, conversation, guard_result
        )

    async def _finalize_input_block(
        self, command: SendMessageCommand, conversation, guard_result
    ) -> AgentResponse:
        """從 blocked GuardResult 組攔截回應（persist + trace），regex guard 與
        分類器攻擊共用（test_mode 不落庫）。"""
        assistant_msg = None
        t_persist = AgentTraceCollector.offset_ms()
        if not command.test_mode:
            conversation.add_message("user", command.message)
            assistant_msg = conversation.add_message(
                "assistant", guard_result.blocked_response
            )
            _bump_conversation_counters(conversation)
            await self._conversation_repo.save(conversation)
        # 持久化 trace（含 guard_input_blocked 紅節點），讓 admin
        # 觀測頁 / Studio canvas 能看到攔截 DAG
        g_trace_id, g_nodes = await self._persist_agent_trace(
            conversation_id=conversation.id.value,
            message_id=(
                assistant_msg.id.value if assistant_msg else None
            ),
            latency_ms=0,
            source=command.identity_source or "web",
            persist=not command.test_mode,
            persist_started_ms=t_persist,
        )
        return AgentResponse(
            answer=guard_result.blocked_response,
            conversation_id=conversation.id.value,
            guard_blocked="input",
            guard_rule_matched=guard_result.rule_matched,
            trace_id=g_trace_id if command.test_mode else None,
            trace_nodes=g_nodes if command.test_mode else None,
        )

    async def _resolve_current_version_id(
        self, bot_id: str | None
    ) -> str | None:
        """Issue #54 §13.6 — 當前線上設定版本 id（usage 打標用，fail-open）。"""
        if not bot_id or self._config_version_repo is None:
            return None
        try:
            current = await self._config_version_repo.find_current(bot_id)
            return current.id if current else None
        except Exception:
            logger.warning("config_version.resolve_failed", exc_info=True)
            return None

    @staticmethod
    def _compact_trace_nodes(node_dicts: list[dict]) -> list[dict]:
        """逐題報告/Playground 用的 compact 版：截斷 metadata 長字串
        （llm_input/llm_output 全文不重複存，spec §4.5 體積控制）。"""
        compact: list[dict] = []
        for n in node_dicts:
            node = dict(n)
            meta = node.get("metadata")
            if isinstance(meta, dict):
                node["metadata"] = {
                    k: (v[:500] + "…[truncated]")
                    if isinstance(v, str) and len(v) > 500
                    else v
                    for k, v in meta.items()
                }
            compact.append(node)
        return compact

    async def _persist_agent_trace(
        self,
        conversation_id: str | None = None,
        message_id: str | None = None,
        latency_ms: int = 0,
        source: str = "",
        persist: bool = True,
        persist_started_ms: float | None = None,
    ) -> tuple[str | None, list[dict] | None]:
        """Finalize agent trace；persist=False（test_mode）時不落庫但仍
        finish（清 ContextVar）並回傳 (trace_id, compact_nodes)。"""
        try:
            # Issue #57：收尾節點 + request 根節點，total_ms = 根節點 wall clock
            if persist_started_ms is not None:
                AgentTraceCollector.span("persist", "對話持久化", persist_started_ms)
            total_ms: float | None = float(latency_ms)
            if AgentTraceCollector.wrap_request():
                total_ms = None  # finish 以 request 根節點 end_ms 為準
            trace = AgentTraceCollector.finish(total_ms=total_ms)
            if trace is None:
                return None, None

            node_dicts_compact = self._compact_trace_nodes(
                [n.to_dict() for n in trace.nodes]
            )
            if not persist:
                return trace.trace_id, node_dicts_compact

            session_factory = self._trace_session_factory
            if session_factory is None:
                return trace.trace_id, node_dicts_compact

            trace.conversation_id = conversation_id
            trace.message_id = message_id
            trace.source = source

            from src.infrastructure.db.models.agent_trace_model import (
                AgentExecutionTraceModel,
            )

            # S-Gov.6a: trace-level outcome snapshot
            #   - 任一節點 failed → trace failed
            #   - 任一節點 partial → trace partial
            #   - 全 success → trace success
            node_dicts = [n.to_dict() for n in trace.nodes]
            outcome = _compute_trace_outcome(node_dicts)

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
                outcome=outcome,
            )
            async with session_factory() as session:
                session.add(row)
                await session.commit()
            return trace.trace_id, node_dicts_compact
        except Exception:
            logger.warning("agent_trace.persist_failed", exc_info=True)
            return None, None

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
