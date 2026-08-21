"""LINE Webhook 處理 Use Case"""

import asyncio
import dataclasses
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from src.application.agent.prompt_assembler import inject_runtime_vars
from src.application.agent.send_message_use_case import (
    build_tool_rag_params_map,
)
from src.domain.agent.entity import AgentResponse
from src.domain.agent.services import AgentService
from src.domain.bot.entity import (
    Bot,
    BotLLMParams,
    BotMcpBinding,
    IntentRoute,
    McpServerConfig,
    McpToolMeta,
    ToolRagConfig,
)
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId, BotShortCode
from src.domain.conversation.entity import Conversation
from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import (
    Channel,
    FeedbackId,
    Rating,
)
from src.domain.conversation.history_strategy import (
    ConversationHistoryStrategy,
    HistoryStrategyConfig,
)
from src.domain.conversation.repository import ConversationRepository
from src.domain.line.entity import LinePostbackEvent, LineTextMessageEvent
from src.domain.line.services import LineMessagingService, LineMessagingServiceFactory
from src.domain.shared.cache_service import CacheService
from src.domain.shared.concurrency import ConversationLock
from src.infrastructure.line.flex_contact_builder import build_contact_flex
from src.infrastructure.line.flex_image_carousel_builder import (
    build_image_carousel,
)
from src.infrastructure.logging.setup import get_logger

from ._text_format import strip_markdown_for_line

logger = get_logger(__name__)


@dataclass
class WebhookContext:
    """Phase 1 → Phase 2 的傳遞物件。"""

    bot: Bot
    short_code: str
    line_service: LineMessagingService
    events: list[LineTextMessageEvent] = field(default_factory=list)
    postback_events: list[LinePostbackEvent] = field(default_factory=list)


def _bot_to_json(bot: Bot) -> str:
    """Bot dataclass → JSON str（處理 BotId、BotShortCode 和 datetime）"""
    d = dataclasses.asdict(bot)
    d["id"] = bot.id.value
    d["short_code"] = bot.short_code.value
    d["created_at"] = bot.created_at.isoformat()
    d["updated_at"] = bot.updated_at.isoformat()
    return json.dumps(d, ensure_ascii=False)


def _bot_from_json(raw: str) -> Bot:
    """JSON str → Bot dataclass

    `dataclasses.asdict` 把 nested dataclass 攤平成 dict，反向時必須逐欄重建，
    否則 LINE webhook 取 cached bot 後跑 resolver / builder 會踩 ``getattr(dict, ...)``
    AttributeError（例：tool_configs 漏轉造成 8b9f438 per-tool KB binding 上線後 500）。
    """
    d = json.loads(raw)
    d["id"] = BotId(value=d["id"])
    d["short_code"] = BotShortCode(value=d["short_code"])
    d["llm_params"] = BotLLMParams(**d["llm_params"])
    d["created_at"] = datetime.fromisoformat(d["created_at"])
    d["updated_at"] = datetime.fromisoformat(d["updated_at"])
    d["mcp_servers"] = [
        McpServerConfig(
            **{
                **s,
                "tools": [McpToolMeta(**t) for t in s.get("tools", [])],
            }
        )
        for s in d.get("mcp_servers", [])
    ]
    d["mcp_bindings"] = [BotMcpBinding(**b) for b in d.get("mcp_bindings", [])]
    d["intent_routes"] = [IntentRoute(**r) for r in d.get("intent_routes", [])]
    d["tool_configs"] = {
        name: ToolRagConfig(**cfg) for name, cfg in d.get("tool_configs", {}).items()
    }
    return Bot(**d)


def _format_line_source_lines(sources: list, limit: int = 3) -> list[str]:
    """組 LINE「參考來源」文字行（H10）。

    sources 可能是 Source dataclass 或 dict（DM 快速道透傳的 dm_sources）。原本
    直接 s.score / s.document_name 屬性存取，遇 dict 拋 AttributeError；且該例外在
    reply 送出前拋出（try/finally 之前）→ 使用者收不到任何回覆、對話/trace 未持久化、
    LINE redelivery 重送。此處對兩型都安全取值。
    """
    lines: list[str] = []
    for i, s in enumerate(sources[:limit], 1):
        if isinstance(s, dict):
            score = s.get("score", 0) or 0
            name = s.get("document_name") or s.get("kb_id") or ""
        else:
            score = getattr(s, "score", 0) or 0
            name = getattr(s, "document_name", "") or ""
        lines.append(f"{i}. {name}（{round(score * 100)}%）")
    return lines


class HandleWebhookUseCase:
    def __init__(
        self,
        agent_service: AgentService,
        bot_repository: BotRepository,
        line_service_factory: LineMessagingServiceFactory,
        default_line_service: LineMessagingService | None = None,
        default_tenant_id: str = "",
        default_kb_id: str = "",
        feedback_repository: FeedbackRepository | None = None,
        conversation_repository: ConversationRepository | None = None,
        cache_service: CacheService | None = None,
        cache_ttl: int = 120,
        conversation_lock: ConversationLock | None = None,
        conversation_timeout_minutes: int = 30,
        record_usage_use_case: Any | None = None,
        trace_session_factory: Any | None = None,
        intent_classifier: Any | None = None,
        worker_config_repo: Any | None = None,
        history_strategy: ConversationHistoryStrategy | None = None,
        prompt_guard: Any | None = None,
        query_rag_use_case: Any | None = None,
        dm_image_query_tool: Any | None = None,
    ):
        self._agent_service = agent_service
        self._bot_repository = bot_repository
        self._intent_classifier = intent_classifier
        self._worker_config_repo = worker_config_repo
        self._line_service_factory = line_service_factory
        self._default_line_service = default_line_service
        self._default_tenant_id = default_tenant_id
        self._default_kb_id = default_kb_id
        self._feedback_repo = feedback_repository
        self._conversation_repo = conversation_repository
        self._cache_service = cache_service
        self._cache_ttl = cache_ttl
        self._record_usage = record_usage_use_case
        self._conversation_lock = conversation_lock
        self._conversation_timeout = timedelta(minutes=conversation_timeout_minutes)
        self._trace_session_factory = trace_session_factory
        # Issue: dev-vm 5/4 trace 顯示 LINE 多輪對話 history_loaded_status="lost"
        # — 因為原本沒過 history_strategy 直接傳 raw history list，
        # process_message(history_context="") 讓 react_agent 沒 inject 對話歷史。
        # 加 strategy 後與 send_message_use_case 行為對齊。
        self._history_strategy = history_strategy
        # F2（POC 問題 1）：入口端 input guard，與 intent 分類並行執行。
        # None 時退回 GuardedAgentService 咽喉點串行兜底（行為不變）。
        self._prompt_guard = prompt_guard
        # Issue #50 — workflow 快速道用的檢索管線（direct_retrieval worker）
        self._query_rag = query_rag_use_case
        # 快速道的 DM 圖卡：並行呼叫 DM 工具（signed URL 產生邏輯原封重用）
        self._dm_tool = dm_image_query_tool

    async def _get_bot_cached(self, bot_id: str) -> Bot | None:
        """Redis 快取查 Bot（by ID），預設 120 秒 TTL。"""
        cache_key = f"bot:{bot_id}"
        if self._cache_service is not None:
            cached = await self._cache_service.get(cache_key)
            if cached is not None:
                return _bot_from_json(cached)

        bot = await self._bot_repository.find_by_id(bot_id)
        if bot is not None and self._cache_service is not None:
            await self._cache_service.set(
                cache_key, _bot_to_json(bot), ttl_seconds=self._cache_ttl
            )
        return bot

    async def _get_bot_by_short_code_cached(self, short_code: str) -> Bot | None:
        """Redis 快取查 Bot（by short_code），預設 120 秒 TTL。"""
        cache_key = f"bot:sc:{short_code}"
        if self._cache_service is not None:
            cached = await self._cache_service.get(cache_key)
            if cached is not None:
                return _bot_from_json(cached)

        bot = await self._bot_repository.find_by_short_code(short_code)
        if bot is not None and self._cache_service is not None:
            await self._cache_service.set(
                cache_key, _bot_to_json(bot), ttl_seconds=self._cache_ttl
            )
        return bot

    async def execute(self, events: list[LineTextMessageEvent]) -> None:
        """舊端點：使用預設租戶設定處理 Webhook 事件。"""
        if not self._default_line_service:
            return
        for event in events:
            if not event.message_text:
                continue
            result = await self._agent_service.process_message(
                tenant_id=self._default_tenant_id,
                kb_id=self._default_kb_id,
                user_message=event.message_text,
                kb_ids=[self._default_kb_id],
            )
            message_id = str(uuid4())
            await self._default_line_service.reply_with_quick_reply(
                event.reply_token, strip_markdown_for_line(result.answer), message_id
            )

    @staticmethod
    def _parse_text_events(body_text: str) -> list[LineTextMessageEvent]:
        """從 LINE Webhook body 解析文字訊息事件。"""
        data = json.loads(body_text)
        events: list[LineTextMessageEvent] = []
        for event_data in data.get("events", []):
            if (
                event_data.get("type") == "message"
                and event_data.get("message", {}).get("type") == "text"
            ):
                # M18：群組/room 或未同意條款的事件 source 可能無 userId。原本直接
                # 下標 KeyError → 整批事件解析失敗 → 500 → LINE redelivery，同批
                # 正常 1:1 訊息也一起卡死。無 userId 的事件跳過。
                user_id = (event_data.get("source") or {}).get("userId")
                if not user_id:
                    continue
                events.append(
                    LineTextMessageEvent(
                        reply_token=event_data["replyToken"],
                        user_id=user_id,
                        message_text=event_data["message"]["text"],
                        timestamp=event_data["timestamp"],
                    )
                )
        return events

    @staticmethod
    def _parse_postback_events(body_text: str) -> list[LinePostbackEvent]:
        """從 LINE Webhook body 解析 postback 事件。"""
        data = json.loads(body_text)
        events: list[LinePostbackEvent] = []
        for event_data in data.get("events", []):
            if event_data.get("type") == "postback":
                user_id = (event_data.get("source") or {}).get("userId")
                if not user_id:  # M18：無 userId 的 postback 跳過
                    continue
                events.append(
                    LinePostbackEvent(
                        reply_token=event_data["replyToken"],
                        user_id=user_id,
                        postback_data=event_data["postback"]["data"],
                        timestamp=event_data["timestamp"],
                    )
                )
        return events

    async def prepare_and_reply(
        self,
        short_code: str,
        body_text: str,
        signature: str,
    ) -> "WebhookContext | None":
        """Bot 查詢 → 驗簽 → 解析事件。回傳 context 供後續處理。"""
        bot = await self._get_bot_by_short_code_cached(short_code)
        if bot is None:
            raise ValueError(f"Bot not found: {short_code}")

        if not bot.line_channel_secret:
            raise ValueError(
                f"Bot {short_code} has no LINE channel secret configured"
            )

        line_service = self._line_service_factory.create(
            bot.line_channel_secret,
            bot.line_channel_access_token or "",
        )

        if not await line_service.verify_signature(body_text, signature):
            raise ValueError("Invalid LINE webhook signature")

        events = self._parse_text_events(body_text)
        postback_events = self._parse_postback_events(body_text)

        return WebhookContext(
            bot=bot,
            short_code=short_code,
            line_service=line_service,
            events=events,
            postback_events=postback_events,
        )

    async def process_and_push(self, ctx: "WebhookContext") -> None:
        """RAG + LLM → reply 回覆（使用 reply token，不消耗 Push 配額）。"""
        bot = ctx.bot
        line_service = ctx.line_service

        for event in ctx.events:
            if not event.message_text:
                continue

            lock_key = f"conv_lock:{event.user_id}:{bot.id.value}"

            # Try to acquire conversation lock
            if self._conversation_lock:
                async with self._conversation_lock.acquire(lock_key) as acquired:
                    if not acquired:
                        # Reply via reply_token (free, not push quota)
                        await line_service.reply_text(
                            event.reply_token, bot.busy_reply_message
                        )
                        continue
                    await self._process_single_event(
                        event, bot, line_service, ctx.short_code
                    )
            else:
                await self._process_single_event(
                    event, bot, line_service, ctx.short_code
                )

        for pb_event in ctx.postback_events:
            await self.handle_postback(
                pb_event, bot.tenant_id, line_service
            )

    async def _try_direct_retrieval(
        self,
        *,
        event: LineTextMessageEvent,
        bot: Bot,
        kb_id: str,
        kb_ids: list[str],
        system_prompt: str | None,
        llm_params: dict,
        rerank_metadata: dict,
        history: list | None,
        history_context: str,
        router_context: str,
        enabled_tools: list[str] | None = None,
        tool_rag_params: dict | None = None,
        retrieval_query: str = "",
    ) -> "AgentResponse | None":
        """Issue #50 workflow 快速道：直接檢索 → 門檻判定 → 單次生成。

        回傳 None 代表升級完整 ReAct（檢索 0 筆 / 低分 / 異常）。
        設計依據：67 筆實測中 FAQ 型 worker 15/16 必查且查詢詞≈原文，
        ReAct 決策輪（~2s）對這類 worker 是冗餘 — 意圖分類已回答「要不要查」。

        Issue #51：「查詢詞≈原文」對 follow-up 短句（「價格呢」）不成立 —
        檢索改用意圖分類同步產出的上下文改寫查詢 retrieval_query，
        缺失時退回原文。生成端 history_context 不受影響。
        """
        from src.application.rag.query_rag_use_case import QueryRAGCommand
        from src.infrastructure.observability.agent_trace_collector import (
            AgentTraceCollector,
        )

        threshold = bot.llm_params.rag_score_threshold
        search_query = (retrieval_query or "").strip() or event.message_text
        t_dr = AgentTraceCollector.offset_ms()

        # DM 圖卡（POC 問題：快速道 v1 漏掉 DM 工具 → 圖卡消失）：
        # 與文字檢索「並行」呼叫 DM 工具本體 — image_url 是文件表查詢 +
        # signed URL 產生的結果，不在向量 payload，必須走工具而非併庫檢索
        dm_task = None
        dm_enabled = (
            self._dm_tool is not None
            and "query_dm_with_image" in (enabled_tools or [])
        )
        if dm_enabled:
            dm_params = (tool_rag_params or {}).get(
                "query_dm_with_image", {}
            ) or {}
            dm_kb_ids = dm_params.get("kb_ids") or kb_ids
            dm_task = asyncio.create_task(self._dm_tool.invoke(
                tenant_id=bot.tenant_id,
                kb_id=dm_kb_ids[0] if dm_kb_ids else kb_id,
                query=search_query,
                kb_ids=dm_kb_ids,
                top_k=dm_params.get("rag_top_k")
                or bot.llm_params.rag_top_k,
                score_threshold=dm_params.get("rag_score_threshold")
                or threshold,
            ))

        # M16：快速道文字檢索原本只用 bot 全域 top_k/threshold，忽略 worker 為
        # rag_query 設的 per-tool RAG 參數（DM 工具有讀、rag_query 沒讀）→ 快速道與
        # 升級後的完整 ReAct 路徑檢索結果不一致。改為讀 tool_rag_params["rag_query"]，
        # 缺時退回 bot 全域。
        rq = (tool_rag_params or {}).get("rag_query", {}) or {}
        rq_kb_ids = rq.get("kb_ids") or kb_ids
        rr = None
        if rr is None:
            try:
                rr = await self._query_rag.retrieve(QueryRAGCommand(
                    tenant_id=bot.tenant_id,
                    kb_id=(rq_kb_ids[0] if rq_kb_ids else kb_id),
                    query=search_query,
                    top_k=rq.get("rag_top_k") or bot.llm_params.rag_top_k,
                    score_threshold=(
                        rq.get("rag_score_threshold")
                        if rq.get("rag_score_threshold") is not None
                        else threshold
                    ),
                    kb_ids=rq_kb_ids,
                    rerank_enabled=(
                        rq.get("rerank_enabled")
                        if rq.get("rerank_enabled") is not None
                        else bot.rerank_enabled
                    ),
                    rerank_model=rq.get("rerank_model") or bot.rerank_model,
                    rerank_top_n=rq.get("rerank_top_n") or bot.rerank_top_n,
                ))
            except Exception:
                logger.warning("line.direct_retrieval.error", exc_info=True)
                if dm_task is not None:
                    dm_task.cancel()
                AgentTraceCollector.add_node(
                    node_type="escalated",
                    label="快速道檢索異常 → 升級 ReAct",
                    parent_id=None,
                    start_ms=t_dr,
                    end_ms=AgentTraceCollector.offset_ms(),
                    reason="retrieval_error",
                )
                return None

        # 收斂 DM 結果（失敗不升級 — 文字檢索可能已足夠回答）
        dm_context = ""
        dm_sources: list[dict] = []
        if dm_task is not None:
            try:
                dm_res = await dm_task
                if dm_res and dm_res.get("success"):
                    dm_context = dm_res.get("context") or ""
                    dm_sources = dm_res.get("sources") or []
            except Exception:
                logger.warning(
                    "line.direct_retrieval.dm_error", exc_info=True
                )

        dm_top = max(
            (float(d.get("score") or 0.0) for d in dm_sources),
            default=0.0,
        )
        top_score = max(
            max((s.score for s in rr.sources), default=0.0), dm_top
        )
        AgentTraceCollector.add_node(
            node_type="direct_retrieval",
            label=f"快速道檢索（{len(rr.sources)} 筆，top {top_score:.2f}）",
            parent_id=None,
            start_ms=t_dr,
            end_ms=AgentTraceCollector.offset_ms(),
            chunk_count=len(rr.sources),
            top_score=round(top_score, 4),
            search_query=search_query,
            query_rewritten=search_query != event.message_text,
        )
        if not rr.sources or top_score < threshold:
            AgentTraceCollector.add_node(
                node_type="escalated",
                label="檢索未過門檻 → 升級 ReAct",
                parent_id=None,
                start_ms=AgentTraceCollector.offset_ms(),
                end_ms=AgentTraceCollector.offset_ms(),
                reason="low_score",
                top_score=round(top_score, 4),
            )
            return None

        # 檢索結果注入 system prompt（KB 內容，非使用者輸入；與 ReAct
        # tool result 進入 model context 為同等暴露面），截斷防 token 爆量
        context_block = "\n\n---\n\n".join(
            c for c in rr.chunks if c
        )[:8000]
        if dm_context:
            context_block += (
                "\n\n【DM 型錄相關內容】\n" + dm_context[:4000]
            )
        # 轉真人工具保留（Larry 實測「多少門市」案例：worker prompt 教
        # 模型查不到就呼叫 transfer_to_human_agent，快速道拔光工具後
        # 模型把工具名稱當文字裸吐）。正常回答仍是 1 次呼叫（不呼叫工具
        # 即結束）；答不出來時可真正轉真人 → 聯絡按鈕與 ReAct 一致
        fast_tools = (
            ["transfer_to_human_agent"]
            if "transfer_to_human_agent" in (enabled_tools or [])
            else []
        )
        fast_prompt = (
            (system_prompt or "")
            + "\n\n【知識庫檢索結果（依相關度排序）】\n"
            + context_block
            + "\n【檢索結果結束】\n"
            + "請依上述檢索結果回答使用者問題；"
            + "結果未涵蓋時誠實告知並引導聯絡客服，禁止編造。"
            + (
                "檢索工具已由系統代為執行完畢，"
                "除 transfer_to_human_agent（轉真人）外無其他可用工具；"
                if fast_tools
                else "本回覆模式下無任何可用工具；"
            )
            + "嚴禁在回覆文字中輸出任何工具名稱。"
        )
        # 快速道：無檢索工具可綁 → 正常情況恰好一次 LLM 呼叫；
        # 沿用 process_message 保留 output guard / trace / parsing 全套機制
        result = await self._agent_service.process_message(
            tenant_id=bot.tenant_id,
            kb_id=kb_id,
            user_message=event.message_text,
            kb_ids=kb_ids,
            system_prompt=fast_prompt,
            enabled_tools=fast_tools,
            llm_params=llm_params,
            metadata=rerank_metadata,
            history=history,
            history_context=history_context,
            router_context=router_context,
            # 轉真人工具靠這個 URL 產生聯絡卡；漏傳 → tool 回 contact=None
            # → 有「請點下方按鈕」文字卻沒按鈕（2026-08-17「我要退費」實測）
            customer_service_url=bot.customer_service_url,
            max_tool_calls=1,
            bot_id=bot.id.value,  # L9：output guard_logs 補 bot 歸因
        )
        # 快速道的檢索來源回填（無 tool call → agent 不會帶 sources），
        # 供 LINE 回覆的來源顯示與對話 retrieved_chunks 持久化
        if result is not None and not result.sources:
            # DM sources 為 dict（含 image_url），下游 reply builder 與
            # 持久化皆支援 dict/Source 混用（見 image_sources 組裝處註解）
            result.sources = list(rr.sources) + list(dm_sources)
        return result

    @staticmethod
    async def _show_loading_safe(
        line_service: LineMessagingService, user_id: str
    ) -> None:
        """背景執行 loading 動畫，失敗僅記 log（fail-open 語義不變）。"""
        try:
            await line_service.show_loading(user_id, 20)
        except Exception:
            logger.warning("line.show_loading_failed", exc_info=True)

    async def _resolve_conversation(
        self, user_id: str, bot: Bot
    ) -> Conversation:
        """Find or create conversation for a LINE user, with timeout segmentation."""
        if self._conversation_repo:
            existing = await self._conversation_repo.find_latest_by_visitor(
                user_id, bot.id.value
            )
            if existing and existing.messages:
                last_msg = existing.messages[-1]
                elapsed = datetime.now(timezone.utc) - last_msg.created_at
                if elapsed < self._conversation_timeout:
                    return existing

        # New conversation
        return Conversation(
            tenant_id=bot.tenant_id,
            bot_id=bot.id.value,
            visitor_id=user_id,
        )

    async def _process_single_event(
        self,
        event: LineTextMessageEvent,
        bot: Bot,
        line_service: LineMessagingService,
        short_code: str,
    ) -> None:
        """Process a single LINE text message event."""
        # Show loading animation — fire-and-forget（Issue #49）：
        # 這是對 LINE API 的一次完整 round-trip，await 會把它整段
        # 計入使用者體感延遲；動畫顯示成功與否不影響主流程（fail-open）。
        loading_task = asyncio.create_task(
            self._show_loading_safe(line_service, event.user_id)
        )
        # 保留引用避免 task 被 GC；主流程遠長於 loading 呼叫，不需 await
        self._pending_loading_task = loading_task

        t0 = time.monotonic()

        # Issue #49 斷點儀表：trace 從 t0 起算。之前 collector 在
        # process_message 內才啟動，前置 ~1.4s（歷史載入/守門/意圖分類）
        # 在 trace 中整塊不可見，只能用 total 減總推回。現在各段獨立成節點。
        from src.infrastructure.observability.agent_trace_collector import (
            AgentTraceCollector,
        )
        AgentTraceCollector.start(
            tenant_id=bot.tenant_id,
            agent_mode="react",
            llm_model=bot.llm_model,
            llm_provider=bot.llm_provider,
            bot_id=bot.id.value,
        )

        t_hist = AgentTraceCollector.offset_ms()
        # Resolve conversation (timeout-based segmentation)
        conversation = await self._resolve_conversation(event.user_id, bot)

        # Extract history from existing conversation
        history = conversation.messages if conversation.messages else None

        # 將 raw history list 過 history_strategy 轉成 LLM 可用的字串。
        # 行為對齊 send_message_use_case._resolve_history (L464-512)，
        # inline 而非抽 service — 避免 refactor 動到 working API path。
        # Defensive：策略對非空 history 仍吐空字串時 fallback _format_messages。
        history_context = ""
        router_context = ""
        if self._history_strategy and history:
            cfg = HistoryStrategyConfig(
                history_limit=bot.llm_params.history_limit,
                recent_turns=3,
            )
            ctx = await self._history_strategy.process(history, cfg)
            history_context = ctx.respond_context
            router_context = ctx.router_context
            if history and not history_context:
                from src.infrastructure.conversation.sliding_window_strategy import (
                    _format_messages,
                )
                history_context = _format_messages(
                    history[-bot.llm_params.history_limit :]
                )
                logger.warning(
                    "line.history.strategy_empty_fallback",
                    strategy=self._history_strategy.name,
                    history_len=len(history),
                    fallback_chars=len(history_context),
                )

        AgentTraceCollector.add_node(
            node_type="history_load",
            label="載入對話歷史",
            parent_id=None,
            start_ms=t_hist,
            end_ms=AgentTraceCollector.offset_ms(),
            history_len=len(history) if history else 0,
        )

        llm_params: dict = {
            "temperature": bot.llm_params.temperature,
            "max_tokens": bot.llm_params.max_tokens,
            "frequency_penalty": bot.llm_params.frequency_penalty,
            # Issue #49：reasoning_effort 一直只存在於 Bot 設定端，
            # 聊天路徑沒傳 → gpt-5 系列固定用 provider 預設 medium。
            # LINE 通路對延遲最敏感，率先接通。
            "reasoning_effort": bot.llm_params.reasoning_effort,
        }
        if bot.llm_provider:
            llm_params["provider_name"] = bot.llm_provider
        if bot.llm_model:
            llm_params["model"] = bot.llm_model

        # Resolve MCP servers from bot bindings
        mcp_servers = None
        if bot.mcp_bindings:
            mcp_servers = []
            for binding in bot.mcp_bindings:
                server_cfg = {
                    "url": binding.url,
                    "transport": binding.transport,
                    "registry_id": binding.registry_id,
                }
                if binding.enabled_tools:
                    server_cfg["enabled_tools"] = binding.enabled_tools
                mcp_servers.append(server_cfg)

        # Build rerank metadata so RAG tools inherit Bot's rerank config.
        rerank_metadata: dict[str, Any] = {
            "rerank_enabled": bot.rerank_enabled,
            "rerank_model": bot.rerank_model,
            "rerank_top_n": bot.rerank_top_n,
        }

        # ── Input guard 與 intent 分類「並行」執行（F2，POC 問題 1）──
        # 兩者都是阻塞 LLM 呼叫，串行要付兩段延遲。權衡（Larry 2026-07-16 核可）：
        # 並行代表 classifier 會在 guard 判定前收到原文一次，但 classifier
        # 輸出僅為 worker 選擇（enum），且 guard 命中時其結果直接丟棄。
        guard_task: asyncio.Task[Any] | None = None
        t_guard0 = AgentTraceCollector.offset_ms()
        if self._prompt_guard is not None:
            guard_task = asyncio.create_task(
                self._prompt_guard.check_input(
                    event.message_text,
                    tenant_id=bot.tenant_id,
                    bot_id=bot.id.value,
                    user_id=event.user_id,  # L9：guard_logs 補使用者歸因
                )
            )

        # ── Worker Routing（Subagent 分流；與 Web path 一致） ──
        # 預設用 bot 本體設定
        system_prompt = bot.bot_prompt or None
        enabled_tools = bot.enabled_tools
        kb_ids = bot.knowledge_base_ids
        kb_id = bot.knowledge_base_ids[0] if bot.knowledge_base_ids else ""
        max_tool_calls = bot.max_tool_calls or 5
        tool_rag_params = build_tool_rag_params_map(bot=bot)

        direct_retrieval_worker = None
        rewritten_query = ""
        classifier_attack = False
        if self._worker_config_repo and self._intent_classifier:
            workers = await self._worker_config_repo.find_by_bot_id(
                bot.id.value
            )
            if workers:
                # Token-Gov.7 A: 包 trace node 記錄 intent classifier LLM 時間
                from src.infrastructure.observability.agent_trace_collector import (
                    AgentTraceCollector,
                )
                t_start = AgentTraceCollector.offset_ms()
                # Issue #51：同一次分類呼叫多產出「上下文改寫檢索查詢」，
                # 供快速道 follow-up 短句（「價格呢」）檢索命中正確商品
                # 2026-08-17：同一次呼叫再多產出「攻擊判定」（三行協定）——
                # 純攻擊 → 前置語意閘門回固定文案、不進生成
                outcome = await self._intent_classifier.classify_sanitize(
                    user_message=event.message_text,
                    router_context=router_context,
                    workers=workers,
                    router_model=bot.router_model,
                    # H9：漏傳則分類器 token 以 tenant_id="" 落孤兒帳（計費繞過），
                    # 與 web 通路（send_message_use_case）行為不一致
                    tenant_id=bot.tenant_id,
                    bot_id=bot.id.value,
                )
                matched, rewritten_query = outcome.worker, outcome.query
                classifier_attack = bool(outcome.is_attack)
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
                    classifier_model=bot.router_model,
                    rewritten_query=rewritten_query or None,
                )
                if matched:
                    if matched.worker_prompt:
                        system_prompt = inject_runtime_vars(matched.worker_prompt)
                    if matched.llm_provider:
                        llm_params["provider_name"] = matched.llm_provider
                    if matched.llm_model:
                        llm_params["model"] = matched.llm_model
                    llm_params["temperature"] = matched.temperature
                    llm_params["max_tokens"] = matched.max_tokens
                    max_tool_calls = matched.max_tool_calls
                    if matched.enabled_mcp_ids and mcp_servers:
                        mcp_servers = [
                            s for s in mcp_servers
                            if s.get("name") in matched.enabled_mcp_ids
                            or s.get("registry_id") in matched.enabled_mcp_ids
                        ]
                    if matched.knowledge_base_ids:
                        kb_ids = matched.knowledge_base_ids
                        kb_id = matched.knowledge_base_ids[0]
                    if matched.enabled_tools is not None:
                        enabled_tools = list(matched.enabled_tools)
                    tool_rag_params = build_tool_rag_params_map(
                        bot=bot, worker=matched,
                    )
                    if getattr(matched, "direct_retrieval", False):
                        direct_retrieval_worker = matched
                    rerank_metadata["_worker_routing"] = {
                        "name": matched.name,
                        "llm_model": matched.llm_model or "",
                        "llm_provider": matched.llm_provider or "",
                        "kb_count": len(matched.knowledge_base_ids),
                    }
                    logger.info(
                        "worker_routing.matched",
                        channel="line",
                        worker_name=matched.name,
                        llm_model=matched.llm_model,
                    )

        # ── 收斂並行 guard 結果：命中 → 不進 agent，改用 blocked 回覆，
        # 其餘下游（persist / reply / trace）與 guard 在咽喉點命中時完全一致
        guard_result = None
        if guard_task is not None:
            guard_result = await guard_task
            # 並行節點：end = 收斂點（≈ max(guard, intent)），非 guard 純耗時
            AgentTraceCollector.add_node(
                node_type="input_guard",
                label="輸入安全檢查（∥意圖分類）",
                parent_id=None,
                start_ms=t_guard0,
                end_ms=AgentTraceCollector.offset_ms(),
                parallel=True,
                passed=bool(guard_result.passed),
            )
        if guard_result is not None and not guard_result.passed:
            result = AgentResponse(
                answer=guard_result.blocked_response,
                guard_blocked="input",
                guard_rule_matched=guard_result.rule_matched,
            )
        elif classifier_attack and self._prompt_guard is not None:
            # 前置語意閘門：分類器判純攻擊 → 與 regex 攔截同一份固定文案，
            # 不呼叫檢索與生成（攻擊句不進主模型；拒答 ≈ 分類耗時）
            blocked = await self._prompt_guard.block_by_classifier(
                message=event.message_text,
                tenant_id=bot.tenant_id,
                bot_id=bot.id.value,
                user_id=event.user_id,
            )
            result = AgentResponse(
                answer=blocked.blocked_response,
                guard_blocked="input",
                guard_rule_matched=blocked.rule_matched,
            )
        else:
            if guard_result is not None:
                # 告知 GuardedAgentService 咽喉點：input guard 已在入口跑過，
                # 不要再付一次 LLM roundtrip（見 guarded_agent_service.py）
                rerank_metadata["_input_guard_checked"] = True
            # LINE 通路規範（格式 / 長度 / 角色鎖）在此注入一次，
            # 快速道與完整 ReAct 共用；bot_prompt / worker_prompt 不再各抄一份
            from src.domain.platform.prompt_defaults import (
                LINE_CHANNEL_PROMPT_SUFFIX,
            )
            system_prompt = (system_prompt or "") + LINE_CHANNEL_PROMPT_SUFFIX
            result = None
            if direct_retrieval_worker is not None and self._query_rag and kb_ids:
                # Issue #50 workflow 快速道：檢索過門檻 → 單次生成；
                # 未過門檻 / 異常 → 回傳 None，落回下方完整 ReAct（升級）
                result = await self._try_direct_retrieval(
                    event=event,
                    bot=bot,
                    kb_id=kb_id,
                    kb_ids=kb_ids,
                    system_prompt=system_prompt,
                    llm_params=llm_params,
                    rerank_metadata=rerank_metadata,
                    history=history,
                    history_context=history_context,
                    router_context=router_context,
                    enabled_tools=enabled_tools,
                    tool_rag_params=tool_rag_params,
                    retrieval_query=rewritten_query,
                )
            if result is None:
                result = await self._agent_service.process_message(
                    tenant_id=bot.tenant_id,
                    kb_id=kb_id,
                    user_message=event.message_text,
                    kb_ids=kb_ids,
                    system_prompt=system_prompt,
                    enabled_tools=enabled_tools,
                    llm_params=llm_params,
                    metadata=rerank_metadata,
                    history=history,
                    history_context=history_context,
                    router_context=router_context,
                    rag_top_k=bot.llm_params.rag_top_k,
                    rag_score_threshold=bot.llm_params.rag_score_threshold,
                    tool_rag_params=tool_rag_params,
                    customer_service_url=bot.customer_service_url,
                    mcp_servers=mcp_servers,
                    max_tool_calls=max_tool_calls,
                    bot_id=bot.id.value,  # L9：output guard_logs 補 bot 歸因
                )
        t1 = time.monotonic()

        # Persist agent execution trace
        from src.infrastructure.observability.agent_trace_collector import (
            AgentTraceCollector,
        )
        latency_ms = round((t1 - t0) * 1000)
        trace = AgentTraceCollector.finish(total_ms=float(latency_ms))
        if trace:
            trace.source = "line"
            # Will set conversation_id and message_id after they're created below

        # Save messages to conversation
        user_msg = conversation.add_message("user", event.message_text)
        assistant_msg = conversation.add_message(
            "assistant",
            result.answer,
            tool_calls=[
                {"tool_name": tc.get("tool_name", ""), "reasoning": tc.get("reasoning", "")}
                if isinstance(tc, dict) else
                {"tool_name": tc.tool_name, "reasoning": getattr(tc, "reasoning", "")}
                for tc in result.tool_calls
            ],
            latency_ms=round((t1 - t0) * 1000),
            retrieved_chunks=[
                # 保留完整欄位（包含 dm tool 的 image_url / page_number）
                # 之前手動只挑 3 欄會把 DM 圖卡資訊砍掉 → web/Studio 跨 channel
                # 重看 LINE 對話時看不到 PNG 卡片
                s if isinstance(s, dict) else s.to_dict()
                for s in result.sources
            ] if result.sources else None,
        )

        # Build reply text — optionally append sources
        # LINE 純文字通路：清除 LLM 殘留的 Markdown 符號（prompt 約束的安全網）
        reply_text = strip_markdown_for_line(result.answer)
        if bot.line_show_sources and result.sources:
            source_lines = _format_line_source_lines(result.sources)
            reply_text += "\n\n📚 參考來源：\n" + "\n".join(source_lines)

        message_id = assistant_msg.id.value

        # Build Flex Message cards from MCP tool outputs
        flex_contents = self._extract_flex_from_tool_calls(result.tool_calls)
        extra_messages: list[dict[str, Any]] = [
            {"type": "flex", "altText": alt_text, "contents": flex_json}
            for alt_text, flex_json in flex_contents
        ]

        # Build DM image carousel from query_dm_with_image tool's sources
        # result.sources 可能是 list[Source dataclass]（react_agent_service 重建後）
        # 或 list[dict]（直接從 tool result 透傳）。兩種都要支援。
        # 之前只檢查 isinstance(s, dict) 導致 Source dataclass 路徑下圖卡完全消失。
        image_sources: list[dict[str, Any]] = []
        for s in (result.sources or []):
            if isinstance(s, dict):
                url = s.get("image_url", "")
                payload = s
            else:
                url = getattr(s, "image_url", "") or ""
                payload = s.to_dict() if hasattr(s, "to_dict") else None
            if url and payload is not None:
                image_sources.append(payload)
        if image_sources:
            extra_messages.append({
                "type": "flex",
                "altText": f"找到 {len(image_sources)} 頁 DM 相關內容",
                "contents": build_image_carousel(image_sources),
            })

        # transfer_to_human_agent tool → 附上 Flex 聯絡按鈕
        contact = getattr(result, "contact", None)
        if isinstance(contact, dict) and contact.get("url"):
            extra_messages.append({
                "type": "flex",
                "altText": contact.get("label") or "聯絡客服",
                "contents": build_contact_flex(contact),
            })

        # 空回覆兜底：LINE text message 不接受空字串（400），空文字等於
        # 使用者端無聲失敗。無論上游因何回空（工具觸頂、LLM 空輸出、
        # guard 誤判），一律補一句引導語，寧可罐頭不可沉默。
        if not reply_text.strip():
            logger.warning(
                "line.reply.empty_answer_fallback",
                has_contact=bool(contact),
                has_extra=bool(extra_messages),
            )
            reply_text = (
                "已為您轉接真人客服，請點擊下方按鈕聯繫。"
                if isinstance(contact, dict) and contact.get("url")
                else "抱歉，這題我暫時沒有找到合適的答案，"
                     "請換個方式描述，或輸入「真人客服」由專人為您服務。"
            )

        # ── Issue #49：回覆先行，持久化後移 ──
        # 使用者體感延遲以 reply 送達為終點，存對話 / trace / usage
        # 挪到 reply 之後。放在 finally 保留「reply 失敗時仍持久化」
        # 的語義（與重排前 persist-then-reply 的 durability 一致）。
        try:
            await line_service.reply_with_quick_reply(
                event.reply_token, reply_text, message_id,
                extra_messages=extra_messages or None,
            )
        finally:
            t2 = time.monotonic()

            # Persist conversation + messages
            if self._conversation_repo:
                # S-Gov.6b: bump counters for cron pending-summary detection
                from datetime import datetime, timezone

                conversation.message_count = len(conversation.messages)
                conversation.last_message_at = datetime.now(timezone.utc)
                await self._conversation_repo.save(conversation)

            # Persist agent trace to DB
            if trace and self._trace_session_factory:
                try:
                    from src.application.agent.send_message_use_case import (
                        _compute_trace_outcome,
                    )
                    from src.infrastructure.db.models.agent_trace_model import (
                        AgentExecutionTraceModel,
                    )
                    trace.conversation_id = conversation.id.value
                    trace.message_id = assistant_msg.id.value
                    node_dicts = [n.to_dict() for n in trace.nodes]
                    row = AgentExecutionTraceModel(
                        id=str(uuid4()),
                        trace_id=trace.trace_id,
                        tenant_id=trace.tenant_id,
                        message_id=trace.message_id,
                        conversation_id=trace.conversation_id,
                        agent_mode=trace.agent_mode,
                        source=trace.source,
                        # M20：LINE trace 原本不設 outcome → 恆 NULL，失敗率儀表板
                        # （以 outcome 過濾）看不到 LINE trace，主力通路監控失明。
                        # 呼叫 web 端同一份共用純函式計算（非重寫）。
                        outcome=_compute_trace_outcome(node_dicts),
                        llm_model=trace.llm_model,
                        llm_provider=trace.llm_provider,
                        bot_id=trace.bot_id,
                        nodes=node_dicts,
                        total_ms=trace.total_ms,
                        total_tokens=trace.total_tokens,
                    )
                    async with self._trace_session_factory() as session:
                        session.add(row)
                        await session.commit()
                except Exception:
                    logger.warning("line.trace_persist_failed", exc_info=True)

            # Record token usage
            if self._record_usage and result.usage:
                try:
                    await self._record_usage.execute(
                        tenant_id=bot.tenant_id,
                        request_type="chat_line",
                        usage=result.usage,
                        bot_id=bot.id.value,
                        # H8：result.message_id 對 LINE 恆為 None（僅 send_message
                        # 路徑會設）；正解是本地 message_id = assistant_msg.id.value，
                        # 否則版本成效 metrics 以 message_id join 不到 LINE 訊息。
                        # 註：config_version_id 打標待共用管線抽取（channel-parity
                        # 絞殺者遷移）統一補上，避免在此複製版本解析邏輯。
                        message_id=message_id,
                    )
                except Exception:
                    logger.warning("line.record_usage_error", exc_info=True)

            t3 = time.monotonic()

            logger.info(
                "line.webhook.timing",
                user_id=event.user_id,
                short_code=short_code,
                llm_provider=bot.llm_provider or "(default)",
                llm_model=bot.llm_model or "(default)",
                process_message_ms=round((t1 - t0) * 1000),
                reply_ms=round((t2 - t1) * 1000),
                persist_ms=round((t3 - t2) * 1000),
                # total_ms = 使用者體感（t0 → reply 完成），不含持久化
                total_ms=round((t2 - t0) * 1000),
                answer_len=len(result.answer),
            )

    @staticmethod
    def _extract_flex_from_tool_calls(
        tool_calls: list[dict[str, Any]],
    ) -> list[tuple[str, dict]]:
        """Extract Flex Message JSON from MCP tool outputs.

        Returns list of (alt_text, flex_content) tuples.
        """
        results: list[tuple[str, dict]] = []
        for tc in tool_calls:
            output = tc.get("tool_output", "")
            if not output:
                continue
            try:
                data = json.loads(output) if isinstance(output, str) else output
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(data, dict):
                continue

            # flex_carousel from search_products
            if data.get("flex_carousel"):
                alt_text = "商品搜尋結果"
                results.append((alt_text, data["flex_carousel"]))

            # flex_bubble from contact_customer_service
            if data.get("flex_bubble"):
                alt_text = data.get("message", "客服聯絡資訊")
                results.append((alt_text, data["flex_bubble"]))

        return results

    async def execute_for_bot(
        self,
        short_code: str,
        body_text: str,
        signature: str,
    ) -> None:
        """舊介面相容：一次跑完 prepare + process。"""
        ctx = await self.prepare_and_reply(short_code, body_text, signature)
        if ctx:
            await self.process_and_push(ctx)

    async def handle_postback(
        self,
        event: LinePostbackEvent,
        tenant_id: str,
        line_service: LineMessagingService | None = None,
    ) -> None:
        """處理 LINE Postback 事件（回饋收集 + 追問原因）。"""
        # L8：舊 webhook 端點傳 tenant_id=""，會讓 Feedback(tenant_id="") 落孤兒帳、
        # 在按租戶過濾的報表中消失。空時退回設定的 default_tenant_id。
        tenant_id = tenant_id or self._default_tenant_id
        if not self._feedback_repo:
            return

        parts = event.postback_data.split(":")

        # feedback_reason:{msg_id}:{tag} — 追問原因回覆
        if len(parts) == 3 and parts[0] == "feedback_reason":
            _, message_id, tag = parts
            await self._feedback_repo.update_tags(message_id, [tag])
            if line_service:
                await line_service.reply_text(
                    event.reply_token, "感謝您的回饋，我們會持續改進！"
                )
            return

        # feedback:{msg_id}:{rating} — 讚/倒讚
        if len(parts) != 3 or parts[0] != "feedback":
            return

        _, message_id, rating_str = parts
        try:
            rating = Rating(rating_str)
        except ValueError:
            return

        existing = await self._feedback_repo.find_by_message_id(message_id)
        if existing is not None:
            return

        # Look up conversation_id from message
        conversation_id = ""
        if self._conversation_repo:
            conversation_id = (
                await self._conversation_repo.find_conversation_id_by_message(
                    message_id
                )
            ) or ""

        feedback = Feedback(
            id=FeedbackId(),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=event.user_id,
            channel=Channel.LINE,
            rating=rating,
            comment=None,
            created_at=datetime.now(timezone.utc),
        )
        await self._feedback_repo.save(feedback)

        # thumbs_down → 追問原因
        if rating == Rating.THUMBS_DOWN and line_service:
            await line_service.reply_with_reason_options(
                event.reply_token, message_id
            )
        elif rating == Rating.THUMBS_UP and line_service:
            await line_service.reply_text(
                event.reply_token, "感謝您的回饋！"
            )
