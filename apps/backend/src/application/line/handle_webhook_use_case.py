"""LINE Webhook 處理 Use Case"""

import dataclasses
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from src.domain.agent.services import AgentService
from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId, BotShortCode
from src.domain.conversation.feedback_entity import Feedback
from src.domain.conversation.feedback_repository import FeedbackRepository
from src.domain.conversation.feedback_value_objects import (
    Channel,
    FeedbackId,
    Rating,
)
from src.domain.line.entity import LinePostbackEvent, LineTextMessageEvent
from src.domain.line.services import LineMessagingService, LineMessagingServiceFactory
from src.domain.shared.cache_service import CacheService
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
        cache_service: CacheService | None = None,
        cache_ttl: int = 120,
    ):
        self._agent_service = agent_service
        self._bot_repository = bot_repository
        self._line_service_factory = line_service_factory
        self._default_line_service = default_line_service
        self._default_tenant_id = default_tenant_id
        self._default_kb_id = default_kb_id
        self._feedback_repo = feedback_repository
        self._cache_service = cache_service
        self._cache_ttl = cache_ttl

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
            await self._default_line_service.show_loading(event.user_id)
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
        """Phase 1（在 endpoint handler 直接 await）：

        Bot 查詢 → 驗簽 → 解析事件 → reply「查詢中」。
        回傳 context 供 Phase 2 背景處理，若無需處理回傳 None。
        """
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

        # 立即 reply「查詢中…」— 用戶秒收到
        for event in events:
            if event.message_text:
                await line_service.reply_text(
                    event.reply_token, "查詢中，請稍候…"
                )

        return WebhookContext(
            bot=bot,
            short_code=short_code,
            line_service=line_service,
            events=events,
            postback_events=postback_events,
        )

    async def process_and_push(self, ctx: "WebhookContext") -> None:
        """Phase 2（background task）：RAG + LLM → push 回覆。"""
        bot = ctx.bot
        line_service = ctx.line_service

        for event in ctx.events:
            if not event.message_text:
                continue
            await line_service.show_loading(event.user_id)
            t0 = time.monotonic()

            llm_params: dict = {
                "temperature": bot.llm_params.temperature,
                "max_tokens": bot.llm_params.max_tokens,
                "frequency_penalty": bot.llm_params.frequency_penalty,
            }
            if bot.llm_provider:
                llm_params["provider_name"] = bot.llm_provider
            if bot.llm_model:
                llm_params["model"] = bot.llm_model

            result = await self._agent_service.process_message(
                tenant_id=bot.tenant_id,
                kb_id=bot.knowledge_base_ids[0] if bot.knowledge_base_ids else "",
                user_message=event.message_text,
                kb_ids=bot.knowledge_base_ids,
                system_prompt=bot.system_prompt or None,
                enabled_tools=bot.enabled_tools,
                llm_params=llm_params,
            )
            t1 = time.monotonic()

            message_id = str(uuid4())
            await line_service.push_with_quick_reply(
                event.user_id, result.answer, message_id
            )
            t2 = time.monotonic()

            logger.info(
                "line.webhook.timing",
                user_id=event.user_id,
                short_code=ctx.short_code,
                llm_provider=bot.llm_provider or "(default)",
                llm_model=bot.llm_model or "(default)",
                process_message_ms=round((t1 - t0) * 1000),
                push_ms=round((t2 - t1) * 1000),
                total_ms=round((t2 - t0) * 1000),
                answer_len=len(result.answer),
            )

        for pb_event in ctx.postback_events:
            await self.handle_postback(
                pb_event, bot.tenant_id, line_service
            )

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

        feedback = Feedback(
            id=FeedbackId(),
            tenant_id=tenant_id,
            conversation_id="",
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
