"""SendMessageUseCase + HandleWebhookUseCase lock 整合測試"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.line.handle_webhook_use_case import (
    HandleWebhookUseCase,
    WebhookContext,
)
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId, BotShortCode
from src.domain.line.entity import LineTextMessageEvent
from src.domain.shared.concurrency import ConversationLock


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FakeLock(ConversationLock):
    """Test lock that can be configured to succeed or fail."""

    def __init__(self, acquired: bool = True):
        self._acquired = acquired

    @asynccontextmanager
    async def acquire(self, lock_key, *, timeout=120):
        yield self._acquired


class TestSendMessageUseCaseLock:
    """SendMessageUseCase 鎖定行為測試"""

    def _make_use_case(self, lock: ConversationLock | None = None) -> tuple:
        agent_service = AsyncMock()
        agent_service.process_message = AsyncMock(
            return_value=AgentResponse(answer="ok")
        )
        conv_repo = AsyncMock()
        conv_repo.find_by_id = AsyncMock(return_value=None)
        conv_repo.save = AsyncMock()

        bot = Bot(
            id=BotId(value="bot-1"),
            tenant_id="t1",
            name="Test",
            busy_reply_message="忙碌中",
        )
        bot_repo = AsyncMock()
        bot_repo.find_by_id = AsyncMock(return_value=bot)

        uc = SendMessageUseCase(
            agent_service=agent_service,
            conversation_repository=conv_repo,
            bot_repository=bot_repo,
            conversation_lock=lock,
        )
        return uc, agent_service

    def test_acquired_lock_executes_agent(self):
        """Lock 取得 → 正常執行 agent"""
        uc, agent_svc = self._make_use_case(lock=FakeLock(acquired=True))
        cmd = SendMessageCommand(
            tenant_id="t1",
            message="hello",
            conversation_id="conv-1",
            bot_id="bot-1",
        )
        result = _run(uc.execute(cmd))
        assert result.answer == "ok"

    def test_busy_lock_returns_busy_message(self):
        """Lock 未取得 → 回傳 busy_reply_message"""
        uc, agent_svc = self._make_use_case(lock=FakeLock(acquired=False))
        cmd = SendMessageCommand(
            tenant_id="t1",
            message="hello",
            conversation_id="conv-1",
            bot_id="bot-1",
        )
        result = _run(uc.execute(cmd))
        assert result.answer == "忙碌中"
        agent_svc.process_message.assert_not_called()

    def test_no_lock_executes_normally(self):
        """無 lock → 正常執行"""
        uc, agent_svc = self._make_use_case(lock=None)
        cmd = SendMessageCommand(
            tenant_id="t1",
            message="hello",
            conversation_id="conv-1",
            bot_id="bot-1",
        )
        result = _run(uc.execute(cmd))
        assert result.answer == "ok"

    def test_stream_busy_lock_yields_busy_message(self):
        """Streaming: Lock 未取得 → yield busy token + done"""
        uc, _ = self._make_use_case(lock=FakeLock(acquired=False))
        cmd = SendMessageCommand(
            tenant_id="t1",
            message="hello",
            conversation_id="conv-1",
            bot_id="bot-1",
        )

        async def _collect():
            events = []
            async for event in uc.execute_stream(cmd):
                events.append(event)
            return events

        events = _run(_collect())
        token_events = [
            e for e in events
            if e.get("type") == "token" and "忙碌中" in e.get("content", "")
        ]
        assert len(token_events) > 0
        assert events[-1]["type"] == "done"


class TestHandleWebhookUseCaseLock:
    """HandleWebhookUseCase 鎖定行為測試"""

    def _make_bot(self) -> Bot:
        return Bot(
            id=BotId(value="bot-1"),
            short_code=BotShortCode(value="abc123"),
            tenant_id="t1",
            name="Test Bot",
            llm_provider="openai",
            llm_model="gpt-5",
            knowledge_base_ids=["kb-1"],
            busy_reply_message="稍等喔",
        )

    def _make_use_case(self, lock: ConversationLock | None = None):
        agent_svc = AsyncMock()
        agent_svc.process_message = AsyncMock(
            return_value=AgentResponse(answer="reply")
        )
        bot_repo = AsyncMock()
        line_factory = MagicMock()
        line_service = AsyncMock()
        line_service.show_loading = AsyncMock()
        line_service.reply_text = AsyncMock()
        line_service.reply_with_quick_reply = AsyncMock()

        uc = HandleWebhookUseCase(
            agent_service=agent_svc,
            bot_repository=bot_repo,
            line_service_factory=line_factory,
            conversation_lock=lock,
        )
        return uc, agent_svc, line_service

    def test_acquired_lock_calls_agent(self):
        """Lock 取得 → show_loading + agent"""
        bot = self._make_bot()
        uc, agent_svc, line_service = self._make_use_case(
            lock=FakeLock(acquired=True)
        )
        ctx = WebhookContext(
            bot=bot,
            short_code="abc123",
            line_service=line_service,
            events=[
                LineTextMessageEvent(
                    reply_token="rt-1",
                    user_id="u1",
                    message_text="hello",
                    timestamp=123,
                )
            ],
        )
        _run(uc.process_and_push(ctx))
        line_service.show_loading.assert_called_once()
        agent_svc.process_message.assert_called_once()

    def test_busy_lock_replies_busy(self):
        """Lock 未取得 → reply busy_reply_message"""
        bot = self._make_bot()
        uc, agent_svc, line_service = self._make_use_case(
            lock=FakeLock(acquired=False)
        )
        ctx = WebhookContext(
            bot=bot,
            short_code="abc123",
            line_service=line_service,
            events=[
                LineTextMessageEvent(
                    reply_token="rt-1",
                    user_id="u1",
                    message_text="hello",
                    timestamp=123,
                )
            ],
        )
        _run(uc.process_and_push(ctx))
        line_service.reply_text.assert_called_once_with("rt-1", "稍等喔")
        agent_svc.process_message.assert_not_called()
