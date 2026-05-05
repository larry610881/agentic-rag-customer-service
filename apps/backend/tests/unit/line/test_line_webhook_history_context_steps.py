"""LINE Webhook 歷史上下文 BDD Step Definitions

Regression test for: LINE webhook 沒把 raw history 透過 history_strategy
轉換為 history_context 字串就直接呼叫 process_message — 導致 ReAct
agent 看不到對話歷史，trace 顯示 history_loaded_status="lost"。

Tests target the multi-tenant `_process_single_event` path triggered via
`process_and_push` (the path used by /api/v1/line/{short_code} webhook).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.line.handle_webhook_use_case import (
    HandleWebhookUseCase,
    WebhookContext,
)
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.conversation.entity import Conversation, Message
from src.domain.conversation.value_objects import MessageId
from src.domain.line.entity import LineTextMessageEvent
from src.infrastructure.conversation.sliding_window_strategy import (
    SlidingWindowStrategy,
)

scenarios("unit/line/line_webhook_history_context.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_bot() -> Bot:
    return Bot(
        tenant_id="tenant-history",
        name="History Test Bot",
        line_channel_secret="secret-history",
        line_channel_access_token="access-history",
        knowledge_base_ids=["kb-history"],
        bot_prompt="Test prompt",
    )


def _make_conv_with_messages(bot: Bot, count: int) -> Conversation:
    """Create a Conversation seeded with `count` alternating user/assistant turns."""
    conv = Conversation(
        tenant_id=bot.tenant_id,
        bot_id=bot.id.value,
        visitor_id="U-history",
    )
    user_phrases = ["有沒有掃地機器人", "拖地機器人呢"]
    bot_phrases = [
        "家樂福掃地機器人特價中",
        "拖地機器人也有 DM 優惠頁面",
    ]
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        content = (
            user_phrases[i // 2 % len(user_phrases)]
            if role == "user"
            else bot_phrases[i // 2 % len(bot_phrases)]
        )
        conv.messages.append(
            Message(
                id=MessageId(),
                conversation_id=conv.id.value,
                role=role,
                content=content,
                created_at=datetime.now(timezone.utc),
            )
        )
    return conv


def _build_use_case(context, *, with_strategy: bool = True) -> HandleWebhookUseCase:
    bot = context.get("bot") or _make_bot()
    context["bot"] = bot

    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="OK")
    )

    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)
    mock_bot_repo.find_by_short_code = AsyncMock(return_value=bot)

    mock_line_service = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)

    mock_conv_repo = AsyncMock()
    seeded_conv = context.get("seeded_conv")
    mock_conv_repo.find_latest_by_visitor = AsyncMock(
        return_value=seeded_conv
    )

    history_strategy = SlidingWindowStrategy() if with_strategy else None

    use_case = HandleWebhookUseCase(
        agent_service=mock_agent,
        bot_repository=mock_bot_repo,
        line_service_factory=mock_factory,
        conversation_repository=mock_conv_repo,
        history_strategy=history_strategy,
    )

    context["use_case"] = use_case
    context["mock_agent"] = mock_agent
    context["mock_line_service"] = mock_line_service
    return use_case


def _drive_webhook(context):
    """Trigger _process_single_event via process_and_push entry point."""
    bot = context["bot"]
    use_case = context["use_case"]
    line_service = context["mock_line_service"]
    event = LineTextMessageEvent(
        reply_token="token-history",
        user_id="U-history",
        message_text="新一輪訊息",
        timestamp=1700000000000,
    )
    ctx = WebhookContext(
        bot=bot,
        short_code="hi",
        line_service=line_service,
        events=[event],
        postback_events=[],
    )
    _run(use_case.process_and_push(ctx))


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("對話已有 4 條 user/assistant 訊息")
def given_conv_with_4_messages(context):
    bot = _make_bot()
    context["bot"] = bot
    context["seeded_conv"] = _make_conv_with_messages(bot, 4)


@given("對話無任何先前訊息")
def given_conv_empty(context):
    bot = _make_bot()
    context["bot"] = bot
    context["seeded_conv"] = None  # _resolve_conversation will create empty Conversation


@given("LINE webhook bot 已注入 sliding window history_strategy")
def given_use_case_with_strategy(context):
    _build_use_case(context, with_strategy=True)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("系統處理新一輪 LINE 文字訊息")
def when_process_event(context):
    _drive_webhook(context)


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("Agent 應收到非空的 history_context")
def then_history_context_non_empty(context):
    mock_agent = context["mock_agent"]
    mock_agent.process_message.assert_called_once()
    kwargs = mock_agent.process_message.call_args.kwargs
    history_context = kwargs.get("history_context", "")
    assert history_context, (
        f"Expected non-empty history_context, got {history_context!r}. "
        f"All kwargs: {list(kwargs.keys())}"
    )


@then("history_context 應包含先前訊息的內容")
def then_history_context_includes_prior(context):
    kwargs = context["mock_agent"].process_message.call_args.kwargs
    hc = kwargs.get("history_context", "")
    assert "掃地機器人" in hc or "拖地機器人" in hc, (
        f"history_context missing prior turn keywords: {hc!r}"
    )


@then("Agent 應收到 history_context 為空字串")
def then_history_context_empty(context):
    mock_agent = context["mock_agent"]
    mock_agent.process_message.assert_called_once()
    kwargs = mock_agent.process_message.call_args.kwargs
    history_context = kwargs.get("history_context", "")
    assert history_context == "", (
        f"Expected empty history_context for first turn, got {history_context!r}"
    )
