"""LINE Webhook 處理 Use Case"""

import dataclasses
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from src.domain.agent.services import AgentService
from src.domain.bot.entity import Bot, BotLLMParams
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
from src.domain.conversation.repository import ConversationRepository
from src.domain.line.entity import LinePostbackEvent, LineTextMessageEvent
from src.domain.line.services import LineMessagingService, LineMessagingServiceFactory
from src.domain.shared.cache_service import CacheService
from src.domain.shared.concurrency import ConversationLock
from src.application.agent.prompt_assembler import inject_runtime_vars
from src.application.agent.send_message_use_case import (
    build_tool_rag_params_map,
)
from src.infrastructure.line.flex_image_carousel_builder import (
    build_image_carousel,
)
from src.infrastructure.line.flex_contact_builder import build_contact_flex
from src.infrastructure.logging.setup import get_logger

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
    """JSON str → Bot dataclass"""
    d = json.loads(raw)
    d["id"] = BotId(value=d["id"])
    d["short_code"] = BotShortCode(value=d["short_code"])
    d["llm_params"] = BotLLMParams(**d["llm_params"])
    d["created_at"] = datetime.fromisoformat(d["created_at"])
    d["updated_at"] = datetime.fromisoformat(d["updated_at"])
    return Bot(**d)


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
                event.reply_token, result.answer, message_id
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
                events.append(
                    LineTextMessageEvent(
                        reply_token=event_data["replyToken"],
                        user_id=event_data["source"]["userId"],
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
                events.append(
                    LinePostbackEvent(
                        reply_token=event_data["replyToken"],
                        user_id=event_data["source"]["userId"],
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
        # Show loading animation
        try:
            await line_service.show_loading(event.user_id, 20)
        except Exception:
            logger.warning("line.show_loading_failed", exc_info=True)

        t0 = time.monotonic()

        # Resolve conversation (timeout-based segmentation)
        conversation = await self._resolve_conversation(event.user_id, bot)

        # Extract history from existing conversation
        history = conversation.messages if conversation.messages else None

        llm_params: dict = {
            "temperature": bot.llm_params.temperature,
            "max_tokens": bot.llm_params.max_tokens,
            "frequency_penalty": bot.llm_params.frequency_penalty,
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

        # ── Worker Routing（Subagent 分流；與 Web path 一致） ──
        # 預設用 bot 本體設定
        system_prompt = bot.bot_prompt or None
        enabled_tools = bot.enabled_tools
        kb_ids = bot.knowledge_base_ids
        kb_id = bot.knowledge_base_ids[0] if bot.knowledge_base_ids else ""
        max_tool_calls = bot.max_tool_calls or 5
        tool_rag_params = build_tool_rag_params_map(bot=bot)

        if self._worker_config_repo and self._intent_classifier:
            workers = await self._worker_config_repo.find_by_bot_id(
                bot.id.value
            )
            if workers:
                matched = await self._intent_classifier.classify_workers(
                    user_message=event.message_text,
                    router_context="",
                    workers=workers,
                    router_model=bot.router_model,
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
            rag_top_k=bot.llm_params.rag_top_k,
            rag_score_threshold=bot.llm_params.rag_score_threshold,
            tool_rag_params=tool_rag_params,
            customer_service_url=bot.customer_service_url,
            mcp_servers=mcp_servers,
            max_tool_calls=max_tool_calls,
        )
        t1 = time.monotonic()

        # Persist agent execution trace
        from src.infrastructure.observability.agent_trace_collector import AgentTraceCollector
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
                {"document_name": s.get("document_name", "") if isinstance(s, dict) else s.document_name,
                 "content_snippet": s.get("content_snippet", "") if isinstance(s, dict) else s.content_snippet,
                 "score": s.get("score", 0) if isinstance(s, dict) else s.score}
                for s in result.sources
            ] if result.sources else None,
        )

        # Persist conversation + messages
        if self._conversation_repo:
            await self._conversation_repo.save(conversation)

        # Persist agent trace to DB
        if trace and self._trace_session_factory:
            try:
                from src.infrastructure.db.models.agent_trace_model import AgentExecutionTraceModel
                trace.conversation_id = conversation.id.value
                trace.message_id = assistant_msg.id.value
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
                    nodes=[n.to_dict() for n in trace.nodes],
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
                )
            except Exception:
                logger.warning("line.record_usage_error", exc_info=True)

        # Build reply text — optionally append sources
        reply_text = result.answer
        if bot.line_show_sources and result.sources:
            source_lines = []
            for i, s in enumerate(result.sources[:3], 1):
                score_pct = round(s.score * 100)
                source_lines.append(f"{i}. {s.document_name}（{score_pct}%）")
            reply_text += "\n\n📚 參考來源：\n" + "\n".join(source_lines)

        message_id = assistant_msg.id.value

        # Build Flex Message cards from MCP tool outputs
        flex_contents = self._extract_flex_from_tool_calls(result.tool_calls)
        extra_messages: list[dict[str, Any]] = [
            {"type": "flex", "altText": alt_text, "contents": flex_json}
            for alt_text, flex_json in flex_contents
        ]

        # Build DM image carousel from query_dm_with_image tool's sources
        # (sources 是 list[dict]，每筆若有 image_url 即為 DM 子頁圖卡)
        image_sources = [
            s for s in (result.sources or [])
            if isinstance(s, dict) and s.get("image_url")
        ]
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

        await line_service.reply_with_quick_reply(
            event.reply_token, reply_text, message_id,
            extra_messages=extra_messages or None,
        )

        t2 = time.monotonic()

        logger.info(
            "line.webhook.timing",
            user_id=event.user_id,
            short_code=short_code,
            llm_provider=bot.llm_provider or "(default)",
            llm_model=bot.llm_model or "(default)",
            process_message_ms=round((t1 - t0) * 1000),
            reply_ms=round((t2 - t1) * 1000),
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
