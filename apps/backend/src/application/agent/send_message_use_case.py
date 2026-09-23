"""發送訊息用例 — 委託 AgentService 處理，支援對話記憶"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import anyio
import structlog

from src.application.abuse.abuse_control_service import (
    AbuseBlockedError,
    AbuseControlService,
    apply_conservative_mode,
)
from src.application.agent.guard_responses import blocked_input_response
from src.application.agent.intent_classifier import IntentClassifier
from src.application.agent.mcp_server_resolver import McpServerResolver
from src.application.agent.output_format import (
    FinalizedAnswer,
    OutputSpec,
    append_prompt_suffix,
    finalize_with_retry,
    merge_usage,
    resolve_guard_blocked,
    resolve_miss_reply,
    resolve_structured_llm_params,
    retrieval_stats,
)
from src.application.agent.prompt_assembler import (
    apply_worker_override,
    resolve_effective_prompt,
)
from src.application.agent.trace_persistence import (
    compute_trace_outcome,
    persist_finished_trace,
)
from src.application.memory.conversation_memory_service import (
    ConversationMemoryService,
)
from src.application.security.guard_pipeline import GuardPipeline
from src.domain.abuse.policy import (
    NO_ABUSE,
    AbuseDecision,
    AbuseSubject,
    SubjectKind,
)
from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.billing.exhaustion import QuotaExhaustedError
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
from src.domain.rag.value_objects import TokenUsage
from src.domain.security.guard_stages import EffectiveGuard
from src.domain.shared.concurrency import ConversationLock
from src.domain.shared.exceptions import DomainException
from src.domain.usage.category import UsageCategory
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
def resolve_allow_rerank(bot: Any) -> bool:
    """Issue #92：rerank 由 `rerank_enabled` 決定，不再被 `mode` 覆蓋。

    舊版是 `allow_rerank = not is_fast and not is_kb`——後台開關打開也無效且無提示。
    現在只看設定本身；要走「最短路徑」就把 `rerank_enabled` 關掉（情境預設會幫你填）。
    """
    return bool(getattr(bot, "rerank_enabled", False))


def _effective(bot_cfg: dict) -> str:
    """取 effective prompt；缺鍵時即時由 system_prompt / bot_prompt 兩層組裝。

    Issue #91：設定字典可能由其他路徑（測試、快速道 fast_cfg）建立，
    這裡保證永遠拿得到組裝結果，且平台防護層不會因為少一個鍵而消失。
    """
    return bot_cfg.get("effective_prompt") or resolve_effective_prompt(bot_cfg)


# Issue #74：通路轉接器宣告的身分來源 → 用量類別（預檢與記帳同一張表）
_IDENTITY_SOURCE_CATEGORY: dict[str, str] = {
    "widget": UsageCategory.CHAT_WIDGET.value,
    "line": UsageCategory.CHAT_LINE.value,
}

_REFUND_METADATA_MARKER = "__refund_metadata"


# channel-parity 二-2：trace outcome 計算與持久化移到 trace_persistence（三通路共用）；
# 保留舊名供既有 import
_compute_trace_outcome = compute_trace_outcome


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
    output: dict[str, Any] | None = None,
    display_text: str | None = None,
    retrieval: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """聚合 tool 產生的 rich payload。全部為空時回傳 None，
    讓下游歷史對話可還原 contact/sources，LINE 路徑不受影響。

    Issue #70：``output``（json 格式解析後物件）、``display_text``（文字通路顯示欄位）、
    ``retrieval``（快速道 / kb 檢索統計）只在有值時加入，既有 payload 形狀不變。"""
    if (
        not contact and not sources
        and output is None and not display_text and not retrieval
    ):
        return None
    payload: dict[str, Any] = {"contact": contact, "sources": sources}
    if output is not None:
        payload["output"] = output
    if display_text:
        payload["display_text"] = display_text
    if retrieval:
        payload["retrieval"] = retrieval
    return payload


@dataclass(frozen=True)
class SendMessageCommand:
    tenant_id: str
    kb_id: str = ""
    message: str = ""
    conversation_id: str | None = None
    bot_id: str | None = None
    visitor_id: str | None = None
    identity_source: str | None = None  # "widget" | "line"
    # Issue #68 P7：異常控管主體（router 依通路填；None = 不控管）
    subject_kind: str | None = None
    subject_id: str | None = None
    client_ip: str | None = None  # P7d：IP 聚合層（LINE 無）
    # Issue #54 Phase C — 影子執行（閘門驗證 / Playground）
    config_override: dict | None = None   # draft 快照 overlay（spec §13.3）
    test_mode: bool = False               # 六面隔離：不落庫、不 memory、不線上 eval
    history_override: list[dict] | None = None  # [{role, content}] 取代 DB 歷史
    # Issue #96：記帳分類（None = 依 identity_source 決定）與 eval run 歸因；
    # 記帳在 use case 內完成，三通路共用，router 不再事後補記（M12）
    usage_request_type: str | None = None
    usage_run_id: str | None = None


@dataclass
class _StreamState:
    """串流生成段累積的狀態（Issue #99 一-6：_stream_generate 與呼叫端共用）。"""

    full_answer: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    sources_list: list[dict[str, Any]] = field(default_factory=list)
    contact_payload: dict[str, Any] | None = None
    refund_step_value: str | None = None
    usage_event: dict[str, Any] | None = None


class SendMessageUseCase:
    def __init__(
        self,
        agent_service: AgentService,
        conversation_repository: ConversationRepository,
        bot_repository: BotRepository | None = None,
        history_strategy: ConversationHistoryStrategy | None = None,
        config_fingerprint: Any | None = None,
        direct_retrieval_service: Any | None = None,
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
        abuse_control: AbuseControlService | None = None,
        worker_config_repo: WorkerConfigRepository | None = None,
        prompt_guard: Any | None = None,
        tenant_repository: "TenantRepository | None" = None,
        config_version_repository: Any | None = None,
        quota_preflight: Any | None = None,
        guard_provider: Any | None = None,
        record_usage_use_case: Any | None = None,
        token_estimator: Callable[[str], int] | None = None,
    ) -> None:
        self._agent_service = agent_service
        self._conversation_repo = conversation_repository
        self._bot_repo = bot_repository
        self._history_strategy = history_strategy
        # Issue #60：有效設定指紋紀錄器（None 時不打標）
        self._config_fingerprint = config_fingerprint
        # Issue #61：快速道共用服務（channel-parity：web / widget 與 LINE 同一份）
        self._direct_retrieval = direct_retrieval_service
        self._debug = debug
        self._trace_session_factory = trace_session_factory
        self._sys_prompt_repo = system_prompt_config_repository
        self._mcp_registry_repo = mcp_registry_repo
        self._encryption = encryption_service
        self._resolve_identity = resolve_identity_use_case
        self._load_memory = load_memory_use_case
        self._extract_memory = extract_memory_use_case
        # channel-parity 二-6：記憶載入 / 萃取三通路共用（LINE 同一份）
        self._memory = ConversationMemoryService(
            resolve_identity=resolve_identity_use_case,
            load_memory=load_memory_use_case,
            extract_memory=extract_memory_use_case,
        )
        self._intent_classifier = intent_classifier
        self._abuse_control = abuse_control
        self._worker_config_repo = worker_config_repo
        self._conversation_lock = conversation_lock
        self._prompt_guard = prompt_guard
        self._record_usage = record_usage_use_case  # Issue #96
        self._token_estimator = token_estimator  # Issue #99：部分計費估算
        self._tenant_repo = tenant_repository
        self._config_version_repo = config_version_repository
        # Issue #74：共用配額預檢（web / widget / LINE / 背景任務同一份）
        self._quota_preflight = quota_preflight
        # Issue #75：防護階段閘門的 provider（web / widget / LINE 同一份 helper；
        # 未注入時全部階段開啟 = #75 之前的行為）
        self._guard_provider = guard_provider

    @property
    def _guard_pipeline(self) -> GuardPipeline:
        """Issue #75：無狀態閘門，每次依當下的 guard / provider / classifier 組成
        （測試會在建構後換掉 _prompt_guard，或以 __new__ 略過 __init__）。"""
        return GuardPipeline(
            getattr(self, "_prompt_guard", None),
            getattr(self, "_guard_provider", None),
            getattr(self, "_intent_classifier", None),
        )

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
            # Issue #91 分層：system_prompt = 平台防護層（不可取代）、
            # bot_prompt = bot 層（worker 命中時被取代）、
            # effective_prompt = 兩層組裝後送模型的字串。三者不可混用。
            "system_prompt": None,
            "bot_prompt": "",
            "effective_prompt": "",
            "llm_params": None,
            "kb_id": command.kb_id,
            "history_limit": None,
            "enabled_tools": None,
            "rag_top_k": None,
            "rag_score_threshold": None,
            "show_sources": True,
        }
        if not (command.bot_id and self._bot_repo):
            # No bot — 仍須載入平台防護層（Issue #91：任何路徑都不得缺這一層）
            await self._apply_platform_prompt_only(cfg)
            return cfg
        bot = await self._bot_repo.find_by_id(command.bot_id)
        if bot is None:
            await self._apply_platform_prompt_only(cfg)
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
        cfg["llm_params"] = self._build_bot_llm_params(bot)
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
        # Issue #66：bot profile；fast 時沒有 worker 也走快速道
        cfg["mode"] = getattr(bot, "mode", "deep") or "deep"
        # Issue #70：kb（知識庫問答）也走共用快速道，但未命中不升級（knowledge_only）
        # Issue #92：改讀 bot 層開關，mode 只是標籤
        cfg["_direct_retrieval"] = bool(getattr(bot, "direct_retrieval", False))
        cfg["escalate_on_miss"] = bool(
            getattr(bot, "escalate_on_miss", True)
        )
        cfg["output_format"] = getattr(bot, "output_format", "text") or "text"
        cfg["output_schema"] = getattr(bot, "output_schema", None) or None
        cfg["miss_reply"] = getattr(bot, "miss_reply", "") or ""
        cfg["output_text_field"] = getattr(bot, "output_text_field", "") or "answer"
        cfg["tool_rag_params"] = build_tool_rag_params_map(bot=bot)
        # inline + registry 綁定（channel-parity：與 LINE 共用 McpServerResolver）
        cfg["mcp_servers"] = await McpServerResolver(
            self._mcp_registry_repo, self._encryption
        ).resolve(bot, command.tenant_id)

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
        cfg["eval_depth"] = getattr(bot, "eval_depth", "off")
        cfg["eval_provider"] = getattr(bot, "eval_provider", "")
        cfg["eval_model"] = getattr(bot, "eval_model", "")
        cfg["intent_routes"] = list(getattr(bot, "intent_routes", []))
        # S-KB-Followup.2: bot-level model 空 → fallback tenant default
        # → 空 → 系統 default
        _bot_router_model = getattr(bot, "router_model", "")
        _bot_summary_model = getattr(bot, "summary_model", "")
        _tenant_default_intent = ""
        _tenant_default_summary = ""
        if (not _bot_router_model or not _bot_summary_model) and self._tenant_repo:
            (
                _tenant_default_intent,
                _tenant_default_summary,
            ) = await self._load_tenant_default_models(
                self._tenant_repo, command.tenant_id
            )
        cfg["router_model"] = _bot_router_model or _tenant_default_intent
        cfg["summary_model"] = _bot_summary_model or _tenant_default_summary

        # Issue #91 分層解析：系統層與 bot 層**分開存**，到使用當下才組裝。
        # 舊版是 `bot.base_prompt or sys_cfg.system_prompt`——租戶在後台填一個字
        # 就能把平台防護層整段換掉；`base_prompt` 欄位已隨本次一併移除。
        cfg["_platform_prompt_fallback"] = False
        if self._sys_prompt_repo:
            sys_cfg = await self._sys_prompt_repo.get()
            cfg["system_prompt"] = sys_cfg.system_prompt
            # Issue #91：bot 已無覆蓋平台 prompt 的欄位，永遠走平台設定
            cfg["_platform_prompt_fallback"] = True

        cfg["bot_prompt"] = bot.bot_prompt or ""
        cfg["effective_prompt"] = resolve_effective_prompt(cfg)

        return cfg

    async def _apply_platform_prompt_only(self, cfg: dict[str, Any]) -> None:
        """無 bot 路徑：只載入平台防護層並組裝 effective prompt（Issue #91）。"""
        if self._sys_prompt_repo:
            sys_cfg = await self._sys_prompt_repo.get()
            cfg["system_prompt"] = sys_cfg.system_prompt
            cfg["effective_prompt"] = resolve_effective_prompt(cfg)

    @staticmethod
    def _build_bot_llm_params(bot: Any) -> dict:
        """bot 層 LLM 參數（provider / model 有值才帶入）。"""
        llm_params: dict = {
            "temperature": bot.llm_params.temperature,
            "max_tokens": bot.llm_params.max_tokens,
            "frequency_penalty": bot.llm_params.frequency_penalty,
            # Issue #72 前置：與 LINE 通路對齊，bot 的 reasoning_effort 一併帶入
            # （worker 覆寫以 spread 保留此值；合法性由 provider 端 gate 判斷）
            "reasoning_effort": bot.llm_params.reasoning_effort,
        }
        if bot.llm_provider:
            llm_params["provider_name"] = bot.llm_provider
        if bot.llm_model:
            llm_params["model"] = bot.llm_model
        return llm_params

    @staticmethod
    async def _load_tenant_default_models(
        tenant_repo: "TenantRepository", tenant_id: str
    ) -> tuple[str, str]:
        """租戶層預設 (intent, summary) 模型；查詢失敗或無租戶回空字串。"""
        tenant_default_intent = ""
        tenant_default_summary = ""
        try:
            _tenant = await tenant_repo.find_by_id(tenant_id)
            if _tenant is not None:
                tenant_default_intent = getattr(
                    _tenant, "default_intent_model", ""
                )
                tenant_default_summary = getattr(
                    _tenant, "default_summary_model", ""
                )
        except Exception:
            pass
        return tenant_default_intent, tenant_default_summary

    async def _resolve_and_load_memory(
        self, command: SendMessageCommand, bot_cfg: dict[str, Any]
    ) -> str:
        """Resolve visitor identity and load memory context
        （共用 ConversationMemoryService）。
        """
        return await self._memory.load_prompt(
            tenant_id=command.tenant_id,
            source=command.identity_source,
            external_id=command.visitor_id,
            memory_enabled=bool(bot_cfg.get("memory_enabled", False)),
        )

    def _should_extract_memory(
        self, bot_cfg: dict[str, Any], message_count: int
    ) -> bool:
        """Check if memory extraction should be triggered（共用規則）。"""
        return ConversationMemoryService.should_extract(
            bool(bot_cfg.get("memory_enabled", False)),
            int(bot_cfg.get("memory_extraction_threshold", 3) or 3),
            message_count,
        )

    async def _fire_memory_extraction(
        self,
        command: SendMessageCommand,
        bot_cfg: dict[str, Any],
        conversation: Conversation,
    ) -> None:
        """Fire-and-forget memory extraction（共用 ConversationMemoryService）。"""
        await self._memory.schedule_extraction(
            tenant_id=command.tenant_id,
            source=command.identity_source,
            external_id=command.visitor_id,
            conversation=conversation,
            memory_enabled=bool(bot_cfg.get("memory_enabled", False)),
            threshold=int(bot_cfg.get("memory_extraction_threshold", 3) or 3),
            extraction_prompt=str(bot_cfg.get("memory_extraction_prompt", "") or ""),
            bot_id=conversation.bot_id or "",
        )

    async def _resolve_history(
        self,
        history: list | None,
        history_limit: int | None,
        tenant_id: str = "",
        bot_id: str | None = None,
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
                bot_id=bot_id,  # Issue #73：history_summary 用量歸屬
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

    # ── Issue #68 P7：異常使用者分級控管（三通路共用 service，這裡只接線） ──

    @staticmethod
    def _abuse_subject(command: SendMessageCommand) -> AbuseSubject | None:
        if command.subject_kind and command.subject_id:
            try:
                return AbuseSubject(
                    SubjectKind(command.subject_kind), command.subject_id
                )
            except ValueError:
                return None
        if command.identity_source == "widget" and command.visitor_id:
            return AbuseSubject(SubjectKind.VISITOR, command.visitor_id)
        return None

    @staticmethod
    def _usage_category(command: SendMessageCommand) -> str:
        return _IDENTITY_SOURCE_CATEGORY.get(
            command.identity_source or "", UsageCategory.CHAT_WEB.value
        )

    async def _quota_gate(self, command: SendMessageCommand) -> None:
        """Issue #74：用完即擋 → raise QuotaExhaustedError（影子執行不檢查）。"""
        if self._quota_preflight is None or command.test_mode:
            return
        await self._quota_preflight.ensure_allowed(
            command.tenant_id, self._usage_category(command)
        )

    async def abuse_preflight(self, command: SendMessageCommand) -> AbuseDecision:
        """串流端點在送出 headers 前先問一次；L3+ 直接 raise（→ 429）。"""
        guard = await self._guard_pipeline.effective(command.tenant_id)
        return await self._abuse_gate(command, guard)

    async def _abuse_gate(
        self, command: SendMessageCommand, guard: EffectiveGuard
    ) -> AbuseDecision:
        subject = self._abuse_subject(command)
        if self._abuse_control is None or subject is None or command.test_mode:
            return NO_ABUSE
        if not self._guard_pipeline.abuse_enabled(guard):  # Issue #75：階段關閉
            return NO_ABUSE
        decision = await self._abuse_control.evaluate(
            command.tenant_id, subject, client_ip=command.client_ip
        )
        AgentTraceCollector.set_abuse_level(int(decision.effective_level))
        if decision.blocked:
            raise AbuseBlockedError(decision.retry_after, decision.level)
        return decision

    async def _record_abuse(
        self,
        command: SendMessageCommand,
        guard: EffectiveGuard,
        *,
        guard_hit: bool = False,
        attack: bool = False,
        unrouted: bool = False,
    ) -> None:
        subject = self._abuse_subject(command)
        if self._abuse_control is None or subject is None or command.test_mode:
            return
        if not self._guard_pipeline.abuse_enabled(guard):  # Issue #75：階段關閉
            return
        decision = await self._abuse_control.record(
            command.tenant_id, subject,
            guard_hit=guard_hit, attack=attack, unrouted=unrouted,
            channel=command.identity_source or "web",
            client_ip=command.client_ip,
        )
        AgentTraceCollector.set_abuse_level(int(decision.effective_level))

    @staticmethod
    def _apply_abuse_mode(
        bot_cfg: dict[str, Any], decision: AbuseDecision
    ) -> dict[str, Any]:
        if decision.conservative:
            return apply_conservative_mode(bot_cfg)
        return bot_cfg

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
        guard: EffectiveGuard | None = None,
    ) -> dict[str, Any]:
        """Worker routing: classify → override bot_cfg with worker settings.

        Returns bot_cfg unchanged if no workers or no match.
        """
        if guard is None:
            guard = await self._guard_pipeline.effective(
                tenant_id, bot_cfg.get("_bot")
            )
        async def _attack_check_only() -> dict[str, Any]:
            """Issue #92：沒有 worker 就不分流（原本由 mode == "kb" 強制）。

            Issue #75：「分類器攻擊判定」仍是可勾選階段，
            開啟時不帶 worker 只做攻擊判定；關閉時每題只有 1 次 embedding + 1 次 LLM。
            """
            bot_cfg["_classifier_attack"] = await self._guard_pipeline.kb_attack_check(
                guard,
                message=message,
                router_context=router_context,
                router_model=bot_cfg.get("router_model", ""),
                tenant_id=tenant_id,
                bot_id=bot_cfg.get("bot_id") or None,
                test_mode=test_mode,
            )
            return bot_cfg

        if not self._worker_config_repo or not self._intent_classifier:
            return bot_cfg
        bot_id = bot_cfg.get("bot_id", "")
        if not bot_id:
            return bot_cfg

        workers = await self._worker_config_repo.find_by_bot_id(
            bot_id
        )
        if not workers and not bot_cfg.get("intent_routes"):
            return await _attack_check_only()
        if not workers:
            # No workers configured — also try legacy intent_routes
            intent_routes = bot_cfg.get("intent_routes", [])
            if intent_routes:
                bot_cfg = await self._route_legacy_intent(
                    self._intent_classifier,
                    bot_cfg,
                    intent_routes,
                    message=message,
                    router_context=router_context,
                    tenant_id=tenant_id,
                    bot_id=bot_id,
                    test_mode=test_mode,
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
        # Issue #75：classifier_attack 階段關閉時忽略分類器的攻擊判定
        bot_cfg["_classifier_attack"] = self._guard_pipeline.classifier_attack(
            guard, outcome.is_attack
        )
        bot_cfg["_unrouted"] = matched is None  # Issue #68 P7：連續無法分流計分
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

        return self._apply_matched_worker(bot_cfg, matched, outcome)


    @staticmethod
    async def _route_legacy_intent(
        intent_classifier: IntentClassifier,
        bot_cfg: dict[str, Any],
        intent_routes: list,
        *,
        message: str,
        router_context: str,
        tenant_id: str,
        bot_id: str,
        test_mode: bool,
    ) -> dict[str, Any]:
        """無 worker 時走舊版 intent_routes 分類；命中則只換 bot 層 prompt。"""
        # Token-Gov.7 A: 包 trace node 記錄 intent classifier LLM 時間
        t_start = AgentTraceCollector.offset_ms()
        matched = await intent_classifier.classify(
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
            # Issue #91：只換 bot 層，平台防護層不受影響
            bot_cfg = apply_worker_override(bot_cfg, matched.worker_prompt)
            bot_cfg["effective_prompt"] = resolve_effective_prompt(bot_cfg)
        return bot_cfg

    @staticmethod
    def _apply_matched_worker(
        bot_cfg: dict[str, Any], matched: Any, outcome: Any
    ) -> dict[str, Any]:
        """命中 worker → 以 worker 設定覆寫 bot_cfg（回傳新 dict）。"""
        # Override bot_cfg with worker settings
        # Issue #91：worker 只取代 bot 層，平台防護層原封不動
        cfg = apply_worker_override(bot_cfg, matched.worker_prompt)
        if matched.worker_prompt:
            cfg["effective_prompt"] = resolve_effective_prompt(cfg)
        # M17：temperature/max_tokens 賦值原本在 provider/model 條件內 → worker 沿用
        # bot 模型（不指定 provider/model）時 web 忽略 worker 的取樣參數，但 LINE 無條件
        # 套用 → 同一 worker 兩通路取樣參數/回覆長度不同。移出條件，與 LINE 對齊。
        # Issue #72：worker 沒有自己的 reasoning_effort 欄位 → 以 spread 沿用 bot 的值
        # （含 none），與 LINE 的就地覆寫行為一致；合法性交由 provider 端 gate。
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
        # Issue #61：快速道旗標與分類器改寫查詢，供 _apply_fast_lane 使用
        cfg["_direct_retrieval"] = bool(
            getattr(matched, "direct_retrieval", False)
        ) or bool(cfg.get("_direct_retrieval"))
        cfg["_retrieval_query"] = getattr(outcome, "query", "") or ""

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

    # ── 管線共用小段（非串流 / 串流同一份）──

    @staticmethod
    def _inject_retrieval_metadata(
        metadata: dict[str, Any], bot_cfg: dict[str, Any]
    ) -> None:
        """Inject rerank / retrieval-mode / rewrite / HyDE config for RAG tool."""
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

    @staticmethod
    def _prepend_memory(memory_prompt: str, history_context: str) -> str:
        """長期記憶置於歷史脈絡之前（無記憶時原樣回傳）。"""
        if not memory_prompt:
            return history_context
        return (
            memory_prompt + "\n\n" + history_context
            if history_context
            else memory_prompt
        )

    @staticmethod
    def _apply_fast_lane_metadata(
        bot_cfg: dict[str, Any], metadata: dict[str, Any]
    ) -> None:
        """Issue #92：快速道的檢索能力由各自欄位決定，不再由 mode 壓制。"""
        if bot_cfg.get("_direct_retrieval"):
            metadata["rerank_enabled"] = bool(bot_cfg.get("rerank_enabled"))
            metadata["rag_retrieval_modes"] = ["raw"]

    @staticmethod
    def _with_refund_marker(
        tool_calls: list[dict[str, Any]], refund_step: str | None
    ) -> list[dict[str, Any]]:
        """複製 tool_calls，有 refund_step 時附上內部 metadata marker。"""
        tool_calls_to_save = tool_calls[:]
        if refund_step:
            tool_calls_to_save.append({
                "tool_name": _REFUND_METADATA_MARKER,
                "refund_step": refund_step,
            })
        return tool_calls_to_save

    @staticmethod
    def _apply_output_guard_block(
        response: AgentResponse,
        guard_result: Any,
        bot_cfg: dict[str, Any],
        fin: FinalizedAnswer,
    ) -> FinalizedAnswer:
        """輸出防護未通過 → 以攔截文案（套輸出格式）取代回答；否則原樣回傳 fin。"""
        if guard_result is None or guard_result.passed:
            return fin
        # Issue #85：攔截也要套 bot 的輸出格式。原本回純文字，
        # 導致 output_format=json 的 bot 在防護觸發時破壞契約。
        fin = resolve_guard_blocked(
            OutputSpec.from_cfg(bot_cfg), guard_result.blocked_response
        )
        response.answer = fin.text
        # Sprint A++ Guard UX
        response.guard_blocked = "output"
        response.guard_rule_matched = guard_result.rule_matched
        return fin

    @staticmethod
    def _blocked_done_event(
        trace_id: str | None, nodes: Any, test_mode: bool
    ) -> dict[str, Any]:
        """M10：攔截路徑的 done 事件帶上 trace_id（test_mode 另帶 nodes）。"""
        done: dict[str, Any] = {"type": "done"}
        if trace_id:
            done["trace_id"] = trace_id
        if test_mode and nodes:
            done["trace_nodes"] = nodes
        return done

    async def _save_blocked_turn(
        self, command: SendMessageCommand, conversation: Conversation, reply: str
    ) -> Any:
        """攔截回合：非 test_mode 時存 user + 攔截回覆，回傳 assistant message。"""
        if command.test_mode:
            return None
        conversation.add_message("user", command.message)
        assistant_msg = conversation.add_message("assistant", reply)
        _bump_conversation_counters(conversation)
        await self._conversation_repo.save(conversation)
        return assistant_msg

    @staticmethod
    def _is_kb_miss(fast_plan: Any) -> bool:
        """Issue #70：kb 模式快速道未命中（通路以 miss_reply 回覆）。"""
        return fast_plan is not None and bool(getattr(fast_plan, "miss", False))

    async def _classifier_block_result(
        self,
        command: SendMessageCommand,
        bot_cfg: dict[str, Any],
        guard: EffectiveGuard,
    ) -> Any:
        """分類器判定攻擊時取得攔截結果；未判定攻擊或階段關閉回 None。"""
        if not bot_cfg.get("_classifier_attack"):
            return None
        return await self._guard_pipeline.block_by_classifier(
            guard,
            message=command.message,
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            user_id=command.visitor_id,
            dry_run=command.test_mode,  # H6
        )

    async def _stream_check_input(
        self,
        command: SendMessageCommand,
        guard: EffectiveGuard,
        metadata: dict[str, Any],
    ) -> Any:
        """串流：regex 輸入防護；通過時打 F1 標記。回傳未通過的結果，否則 None。

        Issue #75：regex_input 階段關閉時 pipeline 回 None（視同通過）。
        """
        guard_result = await self._guard_pipeline.check_input(
            guard,
            command.message,
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            user_id=command.visitor_id,
            dry_run=command.test_mode,  # H6
        )
        if guard_result is None:
            return None
        if guard_result.passed:
            metadata["_input_guard_checked"] = True  # F1：咽喉點不重跑
            return None
        return guard_result

    async def _stream_input_guard_blocked(
        self,
        command: SendMessageCommand,
        conversation: Conversation,
        guard: EffectiveGuard,
        guard_result: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """串流：regex 輸入防護命中 → 存對話、送攔截事件、存 trace、done。"""
        await self._record_abuse(command, guard, guard_hit=True)  # Issue #68 P7
        assistant_msg = await self._save_blocked_turn(
            command, conversation, guard_result.blocked_response
        )
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
        yield self._blocked_done_event(gb_trace_id, gb_nodes, command.test_mode)

    async def _stream_classifier_attack_blocked(
        self,
        command: SendMessageCommand,
        conversation: Conversation,
        bot_cfg: dict[str, Any],
        guard: EffectiveGuard,
        gr: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """串流：分類器判定攻擊 → 存對話、送攔截事件、存 trace、done。"""
        await self._record_abuse(command, guard, attack=True)  # Issue #68 P7
        attack_msg = await self._save_blocked_turn(
            command, conversation, gr.blocked_response
        )
        # Issue #85：串流攔截同樣套輸出格式，否則 json bot 的前台解析會爆
        _blocked = resolve_guard_blocked(
            OutputSpec.from_cfg(bot_cfg), gr.blocked_response
        )
        yield {"type": "token", "content": _blocked.text}
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
        yield self._blocked_done_event(  # M10
            atk_trace_id, atk_nodes, command.test_mode
        )

    @staticmethod
    def _fast_plan_stream_events(
        fast_plan: Any, sources_list: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """快速道：生成未帶 sources 時補 sources 事件，並附檢索統計事件。

        回傳 (sources_list, 依序要送出的事件)。
        """
        events: list[dict[str, Any]] = []
        if fast_plan is None:
            return sources_list, events
        if not sources_list:
            sources_list = [
                src.to_dict() if hasattr(src, "to_dict") else src
                for src in fast_plan.sources
            ]
            events.append({"type": "sources", "sources": sources_list})
        # Issue #70：檢索統計獨立事件（done 事件由多處組裝，獨立事件最單純）
        events.append({"type": "retrieval", **(retrieval_stats(fast_plan) or {})})
        return sources_list, events

    @staticmethod
    def _structured_output_event(
        out_spec: OutputSpec, fin: FinalizedAnswer
    ) -> dict[str, Any] | None:
        """json 輸出格式：依驗證結果產生 structured_output(_failed) 事件。"""
        if not out_spec.is_json:
            return None
        if fin.status == "valid":
            return {
                "type": "structured_output",
                "output": fin.parsed,
                "display_text": fin.display_text,
            }
        if fin.status == "invalid":
            return {"type": "structured_output_failed", "error": fin.error}
        return None

    @staticmethod
    def _accumulate_stream_event(st: _StreamState, event: dict[str, Any]) -> bool:
        """把串流事件累積進 st；回 True 表示內部事件、不送給客戶端。"""
        # contact event 不塞進 answer，透過 yield 傳給呼叫者
        if event["type"] == "token":
            st.full_answer += event["content"]
        elif event["type"] == "usage":
            st.usage_event = event  # Issue #96：留給收尾記帳
        elif event["type"] == "tool_calls":
            st.tool_calls = event.get("tool_calls", [])
        elif event["type"] == "sources":
            st.sources_list = event.get("sources", [])
        elif event["type"] == "contact":
            st.contact_payload = event.get("contact")
        elif event["type"] == "refund_step":
            st.refund_step_value = event.get("refund_step")
            return True
        return False

    def _client_stream_event(
        self, event: dict[str, Any], bot_cfg: dict[str, Any]
    ) -> dict[str, Any] | None:
        """客戶端可見的事件形狀；回 None 表示不送出。"""
        # Non-debug: hide "direct" tool_calls; strip reasoning for others
        if event["type"] == "tool_calls" and not self._debug:
            tcs = event.get("tool_calls", [])
            # "direct" means no tool used — nothing to show
            if all(tc.get("tool_name") == "direct" for tc in tcs):
                return None
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
            return None
        return event

    async def execute(self, command: SendMessageCommand) -> AgentResponse:
        response = await self._execute_locked(command)
        # Issue #96：記帳在 use case 內完成（與串流路徑同一個 helper）
        await self._record_turn_usage(
            command,
            response.usage,
            message_id=response.message_id,
            config_version_id=response.config_version_id,
            config_hash=response.config_hash,
        )
        return response

    async def _record_partial_usage(
        self,
        command: SendMessageCommand,
        bot_cfg: dict[str, Any],
        gen_kwargs: dict[str, Any],
        partial_answer: str,
        config_hash: str | None,
    ) -> None:
        """Issue #99：生成中斷線的估算記帳；估算器缺席時用字元數 / 2 保底。"""
        estimate = self._token_estimator or (lambda text: max(1, len(text) // 2))
        prompt_text = "\n".join(
            str(gen_kwargs.get(k) or "")
            for k in (
                "system_prompt",
                "history_context",
                "router_context",
                "user_message",
            )
        )
        usage = TokenUsage(
            model=str(bot_cfg.get("llm_model") or "unknown"),
            input_tokens=max(1, estimate(prompt_text)),
            output_tokens=max(1, estimate(partial_answer)),
            estimated=True,
        )
        await self._record_turn_usage(
            command, usage, message_id=None, config_version_id=None,
            config_hash=config_hash,
        )
        logger.info(
            "stream.partial_usage_recorded", bot_id=command.bot_id,
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
        )

    async def _record_turn_usage(
        self,
        command: SendMessageCommand,
        usage: TokenUsage | None,
        *,
        message_id: str | None,
        config_version_id: str | None,
        config_hash: str | None,
    ) -> None:
        """記帳 fail-open：帳務失敗不得炸使用者請求（spec §7.3）。"""
        if self._record_usage is None or usage is None:
            return
        try:
            await self._record_usage.execute(
                tenant_id=command.tenant_id,
                request_type=(
                    command.usage_request_type or self._usage_category(command)
                ),
                usage=usage,
                bot_id=command.bot_id,
                message_id=message_id,
                run_id=command.usage_run_id,
                config_version_id=config_version_id,
                config_hash=config_hash,
            )
        except Exception:
            logger.exception("send_message.record_usage_error")

    @staticmethod
    def _usage_from_event(event: dict[str, Any] | None) -> TokenUsage | None:
        """串流 usage 事件 → TokenUsage（欄位與 build_usage_event 對齊）。"""
        if not event:
            return None
        return TokenUsage(
            model=event.get("model", "unknown"),
            input_tokens=event.get("input_tokens", 0),
            output_tokens=event.get("output_tokens", 0),
            estimated_cost=event.get("estimated_cost", 0.0),
            cache_read_tokens=event.get("cache_read_tokens", 0),
            cache_creation_tokens=event.get("cache_creation_tokens", 0),
            reasoning_tokens=event.get("reasoning_tokens", 0),
        )

    async def _execute_locked(self, command: SendMessageCommand) -> AgentResponse:
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
        # Issue #75：本回合的有效防護階段（租戶層；bot 層在 bot 設定載入後疊加）
        guard = await self._guard_pipeline.effective(command.tenant_id)
        # Issue #68 P7：L3+ raise（429）；L2 固定文案不進 LLM；L1 稍後套保守模式
        abuse_decision = await self._abuse_gate(command, guard)
        if abuse_decision.fixed_reply:
            return AgentResponse(answer=abuse_decision.reply_text)
        await self._quota_gate(command)  # Issue #74：402 quota_exhausted
        t_conv = AgentTraceCollector.offset_ms()
        conversation = await self._load_or_create_conversation(command)
        AgentTraceCollector.span("conversation_load", "對話載入", t_conv)

        history = conversation.messages if conversation.messages else None
        metadata = self._extract_metadata(conversation)
        metadata["_dry_run_guard"] = command.test_mode  # H6

        t_bot = AgentTraceCollector.offset_ms()
        bot_cfg = await self._load_bot_config(command)
        AgentTraceCollector.span("bot_load", "Bot 設定載入", t_bot)
        guard = self._guard_pipeline.overlay_bot(guard, bot_cfg.get("_bot"))
        self._guard_pipeline.annotate(guard, metadata)

        # Inject rerank config into metadata for RAG tool
        self._inject_retrieval_metadata(metadata, bot_cfg)

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
            command, conversation, metadata, guard, bot_cfg
        )
        if blocked is not None:
            await self._record_abuse(command, guard, guard_hit=True)
            return blocked

        history, history_context, router_context = (
            await self._resolve_history(
                history,
                bot_cfg["history_limit"],
                tenant_id=command.tenant_id,
                bot_id=command.bot_id,
            )
        )

        # Memory: resolve identity + load
        memory_prompt = await self._resolve_and_load_memory(command, bot_cfg)
        history_context = self._prepend_memory(memory_prompt, history_context)

        # Worker routing: classify → override bot_cfg
        bot_cfg = await self._resolve_worker_config(
            bot_cfg, command.message, router_context,
            tenant_id=command.tenant_id,
            test_mode=command.test_mode,  # M14：影子執行不記生產分類 token
            guard=guard,
        )

        # H11：分類器語意攻擊短路（與 LINE 對等）——攻擊句不進生成模型。
        # Issue #75：kb 模式的攻擊判定也在此短路（不進檢索 / 生成）
        attack_block = await self._check_classifier_attack(
            command, conversation, bot_cfg, guard
        )
        if attack_block is not None:
            await self._record_abuse(command, guard, attack=True)
            return attack_block

        # Issue #60：prompt 組裝完成 → 有效設定指紋（trace / usage 打標）
        config_hash = await self._fingerprint_config(command, bot_cfg)

        # Issue #61：快速道（direct_retrieval worker）→ 直接檢索、單次生成
        bot_cfg, fast_plan = await self._apply_fast_lane(command, bot_cfg)
        # Issue #92：快速道的檢索能力由各自欄位決定，不再由 mode 壓制
        self._apply_fast_lane_metadata(bot_cfg, metadata)

        # Issue #68 P7：正常回合也計分（連續無法分流 / 節奏），並套 L1 保守模式
        await self._record_abuse(
            command, guard, unrouted=bool(bot_cfg.get("_unrouted"))
        )
        bot_cfg = self._apply_abuse_mode(bot_cfg, abuse_decision)

        # Issue #70：kb 模式未命中 → 固定話術，不呼叫生成模型
        if self._is_kb_miss(fast_plan):
            return await self._finalize_kb_miss(
                command, conversation, bot_cfg, fast_plan, config_hash
            )

        # Propagate worker routing info to agent service (for trace visualization)
        if bot_cfg.get("_worker_matched_info"):
            metadata["_worker_routing"] = bot_cfg["_worker_matched_info"]

        # Issue #70：輸出格式（A 級 response_schema / B 級 json_object + schema 進
        # prompt / C 級只進 prompt）——快速道與完整 ReAct 同一份決策
        bot_cfg, out_spec = self._apply_output_format(bot_cfg)
        gen_kwargs = self._generation_kwargs(
            command, bot_cfg, history, history_context, router_context, metadata,
        )

        t0 = time.perf_counter()
        response = await self._agent_service.process_message(**gen_kwargs)

        async def _retry(instruction: str) -> str:
            second = await self._agent_service.process_message(**{
                **gen_kwargs,
                "system_prompt": append_prompt_suffix(
                    gen_kwargs["system_prompt"], instruction
                ),
            })
            merge_usage(response, second)
            return second.answer

        # json：驗證 → 失敗重試一次 → 仍失敗回未命中話術；plain_text：剝 Markdown
        fin = await finalize_with_retry(out_spec, response.answer, retry=_retry)
        response.answer = fin.text
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if fast_plan is not None and not response.sources:
            response.sources = list(fast_plan.sources)

        retrieved_chunks = (
            [s.to_dict() for s in response.sources]
            if response.sources
            else None
        )

        tool_calls_to_save = self._with_refund_marker(
            response.tool_calls, response.refund_step
        )

        # ── Prompt Guard: output check（Issue #75：output_guard 階段關閉時不跑）──
        guard_result = await self._guard_pipeline.check_output(
            guard,
            response.answer,
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            user_id=command.visitor_id,
            user_message=command.message,
            dry_run=command.test_mode,  # H6
        )
        fin = self._apply_output_guard_block(response, guard_result, bot_cfg, fin)

        structured_content = _build_structured_content(
            contact=response.contact,
            sources=retrieved_chunks,
            output=fin.parsed,
            display_text=fin.display_text,
            retrieval=retrieval_stats(fast_plan),
        )
        response.structured_output = fin.parsed  # Issue #94

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
        response.config_hash = config_hash

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
        guard = await self._guard_pipeline.effective(command.tenant_id)  # Issue #75
        abuse_decision = await self._abuse_gate(command, guard)  # Issue #68 P7
        if abuse_decision.fixed_reply:
            yield {"type": "token", "content": abuse_decision.reply_text}
            yield {"type": "done"}
            return
        try:
            await self._quota_gate(command)  # Issue #74
        except QuotaExhaustedError as exc:
            yield {"type": "quota_exhausted", "content": exc.message}
            yield {"type": "done"}
            return
        t_conv = AgentTraceCollector.offset_ms()
        conversation = await self._load_or_create_conversation(command)
        AgentTraceCollector.span("conversation_load", "對話載入", t_conv)

        history = conversation.messages if conversation.messages else None
        metadata = self._extract_metadata(conversation)
        metadata["_dry_run_guard"] = command.test_mode  # H6

        t_bot = AgentTraceCollector.offset_ms()
        bot_cfg = await self._load_bot_config(command)
        AgentTraceCollector.span("bot_load", "Bot 設定載入", t_bot)
        guard = self._guard_pipeline.overlay_bot(guard, bot_cfg.get("_bot"))
        self._guard_pipeline.annotate(guard, metadata)

        # Inject rerank config into metadata for RAG tool
        self._inject_retrieval_metadata(metadata, bot_cfg)

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
        # Issue #75：regex_input 階段關閉時 pipeline 回 None（視同通過）
        guard_result = await self._stream_check_input(command, guard, metadata)
        if guard_result is not None:
            async for gb_event in self._stream_input_guard_blocked(
                command, conversation, guard, guard_result
            ):
                yield gb_event
            return

        history, history_context, router_context = (
            await self._resolve_history(
                history,
                bot_cfg["history_limit"],
                tenant_id=command.tenant_id,
                bot_id=command.bot_id,
            )
        )

        # Memory: resolve identity + load
        memory_prompt = await self._resolve_and_load_memory(command, bot_cfg)
        history_context = self._prepend_memory(memory_prompt, history_context)

        # Worker routing: classify → override bot_cfg
        bot_cfg = await self._resolve_worker_config(
            bot_cfg, command.message, router_context,
            tenant_id=command.tenant_id,
            test_mode=command.test_mode,  # M14：影子執行不記生產分類 token
            guard=guard,
        )

        # H11：分類器語意攻擊短路（與 LINE 對等）——攻擊句不進生成模型。
        # widget 端由 router 過濾 guard_blocked 事件（H7），只收到固定文案。
        # Issue #75：kb 模式的攻擊判定也在此短路（不進檢索 / 生成）
        gr = await self._classifier_block_result(command, bot_cfg, guard)
        if gr is not None:
            async for atk_event in self._stream_classifier_attack_blocked(
                command, conversation, bot_cfg, guard, gr
            ):
                yield atk_event
            return

        # Issue #60：prompt 組裝完成 → 有效設定指紋（trace / usage 打標）
        config_hash = await self._fingerprint_config(command, bot_cfg)

        # Issue #61：快速道（direct_retrieval worker）→ 直接檢索、單次生成
        bot_cfg, fast_plan = await self._apply_fast_lane(command, bot_cfg)
        # Issue #92：快速道的檢索能力由各自欄位決定，不再由 mode 壓制
        self._apply_fast_lane_metadata(bot_cfg, metadata)

        # Issue #68 P7：正常回合也計分（連續無法分流 / 節奏），並套 L1 保守模式
        await self._record_abuse(
            command, guard, unrouted=bool(bot_cfg.get("_unrouted"))
        )
        bot_cfg = self._apply_abuse_mode(bot_cfg, abuse_decision)

        # Issue #70：kb 模式未命中 → 串流固定話術，不呼叫生成模型
        if self._is_kb_miss(fast_plan):
            async for miss_event in self._stream_kb_miss(
                command, conversation, bot_cfg, fast_plan, config_hash
            ):
                yield miss_event
            return

        async for gen_event in self._stream_generate_turn(
            command, conversation, bot_cfg, guard, fast_plan, metadata,
            history=history,
            history_context=history_context,
            router_context=router_context,
            config_hash=config_hash,
        ):
            yield gen_event

    async def _stream_generate_turn(
        self,
        command: SendMessageCommand,
        conversation: Conversation,
        bot_cfg: dict[str, Any],
        guard: EffectiveGuard,
        fast_plan: Any,
        metadata: dict[str, Any],
        *,
        history: Any,
        history_context: str,
        router_context: str,
        config_hash: str | None,
    ) -> AsyncIterator[dict[str, Any]]:
        """串流生成段：輸出格式決策 → 串流生成 → 快速道補事件 → 收尾。"""
        # Propagate worker routing info to agent service (for trace visualization)
        if bot_cfg.get("_worker_matched_info"):
            metadata["_worker_routing"] = bot_cfg["_worker_matched_info"]

        # Issue #70：輸出格式決策（與非串流同一份）
        bot_cfg, out_spec = self._apply_output_format(bot_cfg)
        gen_kwargs = self._generation_kwargs(
            command, bot_cfg, history, history_context, router_context, metadata,
        )

        # Stream from agent service（Issue #99 一-6：生成段抽成 _stream_generate）
        st = _StreamState()
        t0 = time.perf_counter()
        async for event in self._stream_generate(
            command, bot_cfg, gen_kwargs, config_hash, st
        ):
            yield event
        full_answer = st.full_answer
        tool_calls = st.tool_calls
        sources_list = st.sources_list
        contact_payload = st.contact_payload
        refund_step_value = st.refund_step_value
        usage_event = st.usage_event
        sources_list, fast_events = self._fast_plan_stream_events(
            fast_plan, sources_list
        )
        for fast_event in fast_events:
            yield fast_event
        latency_ms = int((time.perf_counter() - t0) * 1000)

        async for tail_event in self._stream_finish_turn(
            command, conversation, bot_cfg, guard, out_spec, fast_plan,
            full_answer=full_answer,
            tool_calls=tool_calls,
            sources_list=sources_list,
            contact_payload=contact_payload,
            refund_step_value=refund_step_value,
            usage_event=usage_event,
            latency_ms=latency_ms,
            config_hash=config_hash,
        ):
            yield tail_event

    async def _stream_finish_turn(
        self,
        command: SendMessageCommand,
        conversation: Conversation,
        bot_cfg: dict[str, Any],
        guard: EffectiveGuard,
        out_spec: OutputSpec,
        fast_plan: Any,
        *,
        full_answer: str,
        tool_calls: list[dict[str, Any]],
        sources_list: list[dict[str, Any]],
        contact_payload: dict[str, Any] | None,
        refund_step_value: str | None,
        usage_event: dict[str, Any] | None,
        latency_ms: int,
        config_hash: str | None,
    ) -> AsyncIterator[dict[str, Any]]:
        """生成後段：輸出格式 → 輸出防護 → 存對話 / 記帳 / trace → 尾端事件。"""
        # Issue #70：串流不重試（token 已送出）；json 驗證結果以事件告知前端，
        # plain_text 對累積全文剝 Markdown 後持久化（token 本身為原文，可接受）
        fin = await finalize_with_retry(
            out_spec, full_answer, retry=None, fallback=False
        )
        full_answer = fin.text

        # ── Prompt Guard: output check on accumulated answer (Option B) ──
        # 串流結束後檢查整段 full_answer，命中時：
        # - DB 存乾淨版（blocked_response 取代原文）
        # - emit guard_blocked 事件給 Studio 前端，前端覆寫對話泡泡
        # - 端使用者(widget/LINE)透過 router sanitize 拿不到此事件，
        #   即時看到原文無法擋（keyword-based guard 的天花板，已記在 docs）
        # Issue #75：output_guard 階段關閉時 pipeline 回 None
        output_guard = await self._guard_pipeline.check_output(
            guard,
            full_answer,
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            user_id=command.visitor_id,
            user_message=command.message,
            dry_run=command.test_mode,  # H6
        )
        if output_guard is not None and not output_guard.passed:
            full_answer = output_guard.blocked_response
            fin = FinalizedAnswer(text=full_answer)  # 攔截後不再是結構化輸出
            yield {
                "type": "guard_blocked",
                "block_type": "output",
                "rule_matched": output_guard.rule_matched,
                "replacement": full_answer,
            }

        structured_event = self._structured_output_event(out_spec, fin)
        if structured_event is not None:
            yield structured_event

        retrieved_chunks = sources_list if sources_list else None
        structured_content = _build_structured_content(
            contact=contact_payload,
            sources=retrieved_chunks,
            output=fin.parsed,
            display_text=fin.display_text,
            retrieval=retrieval_stats(fast_plan),
        )

        # Save conversation after streaming completes
        # Persist refund_step metadata marker (same logic as execute())
        tool_calls_to_save = self._with_refund_marker(tool_calls, refund_step_value)

        # Issue #96 / #99 一-6：收尾「存對話 → 記帳 → 存 trace」
        # 抽成 _stream_finalize（shielded）
        assistant_msg, cv_id, stream_trace_id, stream_trace_nodes = (
            await self._stream_finalize(
                command, conversation, full_answer, tool_calls_to_save, latency_ms,
                retrieved_chunks, structured_content, usage_event, config_hash,
            )
        )

        if not command.test_mode:
            # Fire-and-forget: memory extraction（test_mode 六面隔離跳過）
            await self._fire_memory_extraction(command, bot_cfg, conversation)

        # Issue #59：線上每輪 LLM 自評已下線（品質驗收走 prompt gate 離線回放）

        async for event in self._stream_tail_events(
            command, conversation, assistant_msg, cv_id, config_hash,
            stream_trace_id, stream_trace_nodes,
        ):
            yield event

    # ── 串流三段（Issue #99 一-6）：生成 / 收尾 / 尾端事件 ──

    async def _stream_generate(
        self,
        command: SendMessageCommand,
        bot_cfg: dict[str, Any],
        gen_kwargs: dict[str, Any],
        config_hash: str | None,
        st: _StreamState,
    ) -> AsyncIterator[dict[str, Any]]:
        """從 agent service 串流事件並累積到 st；生成中斷線以估算補記（#99）。"""
        try:
            async for event in self._agent_service.process_message_stream(**gen_kwargs):
                if self._accumulate_stream_event(st, event):
                    continue  # Internal metadata, not sent to client
                client_event = self._client_stream_event(event, bot_cfg)
                if client_event is None:
                    continue
                yield client_event
        except asyncio.CancelledError:
            # Issue #96 / #99：生成中斷線——供應商已對已生成部分計費，但沒有 usage 數字。
            # 以已串出文字與提示估算 token 補記（estimated=True），訊息不存（另案）。
            logger.info(
                "stream.client_disconnected", phase="generating",
                chars=len(st.full_answer), bot_id=command.bot_id,
            )
            if st.full_answer:
                with anyio.CancelScope(shield=True):
                    await self._record_partial_usage(
                        command, bot_cfg, gen_kwargs, st.full_answer, config_hash
                    )
            raise

    async def _stream_finalize(
        self,
        command: SendMessageCommand,
        conversation: Conversation,
        full_answer: str,
        tool_calls_to_save: list[dict[str, Any]],
        latency_ms: int,
        retrieved_chunks: list[dict[str, Any]] | None,
        structured_content: dict[str, Any] | None,
        usage_event: dict[str, Any] | None,
        config_hash: str | None,
    ) -> tuple[Any, str | None, str | None, list[dict[str, Any]] | None]:
        """收尾「存對話 → 記帳 → 存 trace」（Issue #96 M12）。

        整段包在 shielded scope：客戶端此時斷線，Starlette 的取消會延後到
        本區塊結束後才生效，訊息與用量不會只存一半。
        回傳 (assistant_msg, cv_id, trace_id, trace_nodes)。
        """
        assistant_msg = None
        cv_id: str | None = None
        with anyio.CancelScope(shield=True):
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
                cv_id = await self._resolve_current_version_id(command.bot_id)

            await self._record_turn_usage(
                command,
                self._usage_from_event(usage_event),
                message_id=assistant_msg.id.value if assistant_msg else None,
                config_version_id=cv_id,
                config_hash=config_hash,
            )

            # 在 _persist_agent_trace 之前取 trace_id（finish 後 ContextVar 會被清掉）
            # 用於 SSE done 事件回傳給前端，讓 Studio canvas 等可 fetch 完整 DAG。
            _current_trace = AgentTraceCollector.current()
            stream_trace_id = _current_trace.trace_id if _current_trace else None

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
        return assistant_msg, cv_id, stream_trace_id, stream_trace_nodes

    async def _stream_tail_events(
        self,
        command: SendMessageCommand,
        conversation: Conversation,
        assistant_msg: Any,
        cv_id: str | None,
        config_hash: str | None,
        stream_trace_id: str | None,
        stream_trace_nodes: list[dict[str, Any]] | None,
    ) -> AsyncIterator[dict[str, Any]]:
        """尾端事件：message_id / config_version / config_hash / conversation_id
        / done。
        """
        try:
            if assistant_msg is not None:
                yield {
                    "type": "message_id",
                    "message_id": assistant_msg.id.value,
                }
                if cv_id:
                    yield {
                        "type": "config_version",
                        "config_version_id": cv_id,
                    }
                if config_hash:
                    yield {"type": "config_hash", "config_hash": config_hash}
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
        except asyncio.CancelledError:
            # Issue #96：收尾已完成（訊息與用量都在），只是客戶端沒收到尾端事件
            logger.info(
                "stream.client_disconnected", phase="finalized", bot_id=command.bot_id,
            )
            raise

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
        self,
        command: SendMessageCommand,
        conversation,
        metadata: dict,
        guard: EffectiveGuard,
        bot_cfg: dict[str, Any],
    ) -> AgentResponse | None:
        """Input guard 前置檢查；攔截時回傳攔截回應（test_mode 不落庫）。
        Issue #75：regex_input 階段關閉 → pipeline 回 None → 視同通過。

        `bot_cfg` 只為了輸出格式：攔截也必須守住 bot 的契約，否則
        output_format=json 的 bot 一命中 regex 就吐純文字、前台解析炸掉。"""
        guard_result = await self._guard_pipeline.check_input(
            guard,
            command.message,
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            user_id=command.visitor_id,
            dry_run=command.test_mode,  # H6
        )
        if guard_result is None:
            return None
        if guard_result.passed:
            # F1（POC 問題 1）：input guard 已在此跑過並通過 — 帶標記讓
            # GuardedAgentService 咽喉點跳過重複的 input guard LLM roundtrip
            metadata["_input_guard_checked"] = True
            return None
        return await self._finalize_input_block(
            command, conversation, guard_result, OutputSpec.from_cfg(bot_cfg)
        )

    async def _check_classifier_attack(
        self,
        command: SendMessageCommand,
        conversation,
        bot_cfg: dict,
        guard: EffectiveGuard,
    ) -> AgentResponse | None:
        """H11：分類器判純攻擊 → 與 regex guard 同一份固定文案短路（web/widget）。

        worker routing 的 classify_sanitize 在 _resolve_worker_config 已把 is_attack
        暫存於 bot_cfg（Issue #75：階段關閉時已被壓成 False）；此處走
        block_by_classifier（與 LINE 同副作用與文案）並回傳攔截回應。
        無 workers / 非攻擊 / 無 guard / 階段關閉 → None。
        """
        if not bot_cfg.get("_classifier_attack"):
            return None
        guard_result = await self._guard_pipeline.block_by_classifier(
            guard,
            message=command.message,
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            user_id=command.visitor_id,
            dry_run=command.test_mode,  # H6
        )
        if guard_result is None:
            return None
        return await self._finalize_input_block(
            command, conversation, guard_result, OutputSpec.from_cfg(bot_cfg)
        )

    async def _finalize_input_block(
        self, command: SendMessageCommand, conversation, guard_result,
        output_spec: "OutputSpec | None",
    ) -> AgentResponse:
        """從 blocked GuardResult 組攔截回應（persist + trace），regex guard 與
        分類器攻擊共用（test_mode 不落庫）。"""
        # Issue #94 / channel-parity 二-3：攔截回應與 LINE 同一份組裝
        blocked_resp = blocked_input_response(guard_result, output_spec)
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
        blocked_resp.conversation_id = conversation.id.value
        blocked_resp.trace_id = g_trace_id if command.test_mode else None
        blocked_resp.trace_nodes = g_nodes if command.test_mode else None
        return blocked_resp

    async def _apply_fast_lane(
        self, command: SendMessageCommand, bot_cfg: dict[str, Any]
    ) -> tuple[dict[str, Any], Any | None]:
        """Issue #61：命中 direct_retrieval worker 時走共用快速道。

        回 (bot_cfg', plan)：plan 非 None 表示以快速道 prompt + 工具集單次生成；
        None 表示維持完整 ReAct（未開啟 / 未過門檻 / 異常）。
        """
        if self._direct_retrieval is None or not bot_cfg.get("_direct_retrieval"):
            return bot_cfg, None
        bot_entity = bot_cfg.get("_bot")
        knowledge_only = not bot_cfg.get("escalate_on_miss", True)
        # kb 模式沒綁知識庫也要走 plan（回未命中），其餘沒 KB 直接維持 ReAct
        if bot_entity is None or (not bot_cfg.get("kb_ids") and not knowledge_only):
            return bot_cfg, None
        plan = await self._direct_retrieval.plan(
            tenant_id=command.tenant_id,
            bot=bot_entity,
            kb_id=bot_cfg.get("kb_id", ""),
            kb_ids=list(bot_cfg.get("kb_ids") or []),
            system_prompt=_effective(bot_cfg),
            enabled_tools=bot_cfg.get("enabled_tools"),
            tool_rag_params=bot_cfg.get("tool_rag_params"),
            user_message=command.message,
            retrieval_query=bot_cfg.get("_retrieval_query", ""),
            # Issue #66：fast profile 零額外 LLM；deep 的 worker 快速道依 bot 設定
            # Issue #70：kb 亦零額外 LLM（rerank 關），且未命中不升級（knowledge_only）
            allow_rerank=bool(bot_cfg.get("rerank_enabled")),
            knowledge_only=knowledge_only,
        )
        if plan is None:
            if bot_cfg.get("escalate_on_miss", True):
                # 升級 ReAct 但受 profile 約束：工具上限 2、無 rerank / rewrite / HyDE
                return {
                    **bot_cfg,
                    "max_tool_calls": min(
                        int(bot_cfg.get("max_tool_calls") or 5), 2
                    ),
                    "rerank_enabled": False,
                    "rag_retrieval_modes": ["raw"],
                    "query_rewrite_enabled": False,
                    "hyde_enabled": False,
                }, None
            return bot_cfg, None
        if getattr(plan, "miss", False):
            # Issue #70：kb 未命中——呼叫端以 miss_reply 短路，不進生成模型
            return bot_cfg, plan
        fast_cfg = {
            **bot_cfg,
            # 快速道已把檢索區塊接在 effective_prompt 之後
            "effective_prompt": plan.system_prompt,
            "enabled_tools": plan.enabled_tools,
            "max_tool_calls": plan.max_tool_calls,
            "mcp_servers": [],
        }
        return fast_cfg, plan

    # ── Issue #70：輸出格式 / kb 未命中（三通路共用 helper 在 output_format.py） ──

    @staticmethod
    def _apply_output_format(
        bot_cfg: dict[str, Any],
    ) -> tuple[dict[str, Any], OutputSpec]:
        """依生效的供應商 / 模型能力等級，補 llm_params 與 system prompt 後綴。"""
        spec = OutputSpec.from_cfg(bot_cfg)
        patch, suffix = resolve_structured_llm_params(spec)
        if not patch and not suffix:
            return bot_cfg, spec
        return {
            **bot_cfg,
            "llm_params": {**(bot_cfg.get("llm_params") or {}), **patch},
            "effective_prompt": append_prompt_suffix(
                _effective(bot_cfg), suffix
            ),
        }, spec

    @staticmethod
    def _generation_kwargs(
        command: SendMessageCommand,
        bot_cfg: dict[str, Any],
        history: list | None,
        history_context: str,
        router_context: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """process_message / process_message_stream 共用參數
        （重試時只換 system_prompt）。
        """
        return {
            "tenant_id": command.tenant_id,
            "kb_id": bot_cfg["kb_id"],
            "user_message": command.message,
            "history": history,
            "kb_ids": bot_cfg["kb_ids"],
            "system_prompt": _effective(bot_cfg),
            "llm_params": bot_cfg["llm_params"],
            "metadata": metadata,
            "history_context": history_context,
            "router_context": router_context,
            "enabled_tools": bot_cfg["enabled_tools"],
            "rag_top_k": bot_cfg["rag_top_k"],
            "rag_score_threshold": bot_cfg["rag_score_threshold"],
            "tool_rag_params": bot_cfg.get("tool_rag_params"),
            "customer_service_url": bot_cfg.get("customer_service_url", ""),
            "mcp_servers": bot_cfg.get("mcp_servers"),
            "max_tool_calls": bot_cfg.get("max_tool_calls", 5),
            "bot_id": bot_cfg.get("bot_id", ""),
        }

    async def _finalize_kb_miss(
        self,
        command: SendMessageCommand,
        conversation: Conversation,
        bot_cfg: dict[str, Any],
        plan: Any,
        config_hash: str | None,
    ) -> AgentResponse:
        """kb 模式未命中：以未命中話術落訊息（與正常回覆同一條持久化路徑），
        無 LLM 呼叫故無 usage；trace 已含 kb_miss 節點。"""
        miss = resolve_miss_reply(OutputSpec.from_cfg(bot_cfg))
        structured_content = _build_structured_content(
            contact=None, sources=None, output=miss.parsed,
            display_text=miss.display_text, retrieval=retrieval_stats(plan),
        )
        response = AgentResponse(answer=miss.text, structured_output=miss.parsed)
        assistant_msg = None
        t_persist = AgentTraceCollector.offset_ms()
        if not command.test_mode:
            conversation.add_message("user", command.message)
            assistant_msg = conversation.add_message(
                "assistant", miss.text, latency_ms=0,
                structured_content=structured_content,
            )
            _bump_conversation_counters(conversation)
            await self._conversation_repo.save(conversation)
        response.conversation_id = conversation.id.value
        response.message_id = assistant_msg.id.value if assistant_msg else None
        trace_id, trace_nodes = await self._persist_agent_trace(
            conversation_id=conversation.id.value,
            message_id=response.message_id,
            latency_ms=0,
            source=command.identity_source or "web",
            persist_started_ms=t_persist,
            persist=not command.test_mode,
        )
        if command.test_mode:
            response.trace_id = trace_id
            response.trace_nodes = trace_nodes
            return response
        response.config_version_id = await self._resolve_current_version_id(
            command.bot_id
        )
        response.config_hash = config_hash
        return response

    async def _stream_kb_miss(
        self,
        command: SendMessageCommand,
        conversation: Conversation,
        bot_cfg: dict[str, Any],
        plan: Any,
        config_hash: str | None,
    ) -> AsyncIterator[dict[str, Any]]:
        """kb 模式未命中（串流）：token 事件送話術，其餘事件與正常結束一致。"""
        spec = OutputSpec.from_cfg(bot_cfg)
        miss = resolve_miss_reply(spec)
        structured_content = _build_structured_content(
            contact=None, sources=None, output=miss.parsed,
            display_text=miss.display_text, retrieval=retrieval_stats(plan),
        )
        yield {"type": "token", "content": miss.text}
        if spec.is_json:
            yield {
                "type": "structured_output",
                "output": miss.parsed,
                "display_text": miss.display_text,
            }
        yield {"type": "retrieval", **(retrieval_stats(plan) or {})}
        assistant_msg = None
        t_persist = AgentTraceCollector.offset_ms()
        if not command.test_mode:
            conversation.add_message("user", command.message)
            assistant_msg = conversation.add_message(
                "assistant", miss.text, latency_ms=0,
                structured_content=structured_content,
            )
            _bump_conversation_counters(conversation)
            await self._conversation_repo.save(conversation)
        _current_trace = AgentTraceCollector.current()
        stream_trace_id = _current_trace.trace_id if _current_trace else None
        _, stream_trace_nodes = await self._persist_agent_trace(
            conversation_id=conversation.id.value,
            message_id=assistant_msg.id.value if assistant_msg else None,
            latency_ms=0,
            source=command.identity_source or "web",
            persist=not command.test_mode,
            persist_started_ms=t_persist,
        )
        if assistant_msg is not None:
            yield {"type": "message_id", "message_id": assistant_msg.id.value}
            cv_id = await self._resolve_current_version_id(command.bot_id)
            if cv_id:
                yield {"type": "config_version", "config_version_id": cv_id}
            if config_hash:
                yield {"type": "config_hash", "config_hash": config_hash}
        yield {"type": "conversation_id", "conversation_id": conversation.id.value}
        done_event: dict[str, Any] = {"type": "done"}
        if stream_trace_id:
            done_event["trace_id"] = stream_trace_id
        if command.test_mode and stream_trace_nodes is not None:
            done_event["trace_nodes"] = stream_trace_nodes
        yield done_event

    async def _fingerprint_config(
        self, command: SendMessageCommand, bot_cfg: dict[str, Any]
    ) -> str | None:
        """Issue #60：以解析後的有效設定算指紋，掛到 trace；fail-open。"""
        if self._config_fingerprint is None:
            return None
        try:
            from src.domain.observability.effective_config import EffectiveConfig

            guard = None
            if self._prompt_guard is not None and hasattr(
                self._prompt_guard, "rules_snapshot"
            ):
                snap = await self._prompt_guard.rules_snapshot()
                guard = snap if isinstance(snap, dict) else None
            worker = bot_cfg.get("_worker_matched_info") or {}
            effective = EffectiveConfig(
                channel=command.identity_source or "web",
                bot_id=command.bot_id or "",
                system_prompt=_effective(bot_cfg),
                platform_prompt_fallback=bool(
                    bot_cfg.get("_platform_prompt_fallback", False)
                ),
                worker_name=(
                    str(worker.get("name", "")) if isinstance(worker, dict) else ""
                ),
                llm_provider=str(bot_cfg.get("llm_provider") or ""),
                llm_model=str(bot_cfg.get("llm_model") or ""),
                router_model=str(bot_cfg.get("router_model") or ""),
                llm_params=bot_cfg.get("llm_params") or {},
                retrieval={
                    "modes": list(bot_cfg.get("rag_retrieval_modes") or ["raw"]),
                    "rerank_enabled": bool(bot_cfg.get("rerank_enabled", False)),
                    "rerank_model": bot_cfg.get("rerank_model") or "",
                    "rerank_top_n": bot_cfg.get("rerank_top_n"),
                    "query_rewrite_model": bot_cfg.get("query_rewrite_model") or "",
                    "hyde_model": bot_cfg.get("hyde_model") or "",
                    "kb_ids": list(bot_cfg.get("kb_ids") or []),
                },
                enabled_tools=bot_cfg.get("enabled_tools"),
                max_tool_calls=int(bot_cfg.get("max_tool_calls") or 0),
                guard=guard,
                memory_enabled=bool(bot_cfg.get("memory_enabled", False)),
                extra={"mode": bot_cfg.get("mode", "deep")},
            )
            config_hash = str(await self._config_fingerprint.record(effective))
            AgentTraceCollector.set_config_hash(config_hash)
            return config_hash
        except Exception:
            logger.warning("config_fingerprint.failed", exc_info=True)
            return None

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

            # channel-parity 二-2：與 LINE 同一份持久化
            await persist_finished_trace(
                trace,
                session_factory,
                conversation_id=conversation_id,
                message_id=message_id,
                source=source,
            )
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
