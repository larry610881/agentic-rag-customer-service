"""Widget 聊天 API 驗證 BDD Step Definitions"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId, BotShortCode

scenarios("unit/bot/widget_chat.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_bot_repo():
    return AsyncMock(spec=BotRepository)


@pytest.fixture
def mock_send_message_use_case():
    uc = AsyncMock()

    async def _fake_stream(command):
        yield {"type": "token", "content": "你好！"}
        if command.conversation_id is not None or True:
            yield {"type": "conversation_id", "conversation_id": "conv-001"}
        yield {"type": "done"}

    uc.execute_stream = MagicMock(side_effect=_fake_stream)
    return uc


@given(parsers.parse('租戶 "{tenant_id}" 存在'))
def tenant_exists(context, tenant_id):
    context["tenant_id"] = tenant_id


@given(parsers.parse('機器人 "{bot_id}" 屬於租戶 "{tenant_id}" short_code 為 "{short_code}"'))
def bot_exists(context, mock_bot_repo, bot_id, tenant_id, short_code):
    bot = Bot(
        id=BotId(value=bot_id),
        short_code=BotShortCode(value=short_code),
        tenant_id=tenant_id,
        name="Test Bot",
        description="A test bot",
        is_active=True,
        widget_enabled=False,
        widget_allowed_origins=[],
        widget_keep_history=True,
    )
    context["bot"] = bot
    context["short_code"] = short_code
    mock_bot_repo.find_by_short_code = AsyncMock(return_value=bot)


@given("機器人已啟用 widget 功能")
def bot_widget_enabled(context):
    context["bot"].widget_enabled = True


@given("機器人未啟用 widget 功能")
def bot_widget_disabled(context):
    context["bot"].widget_enabled = False


@given("機器人已停用")
def bot_inactive(context):
    context["bot"].is_active = False


@given(parsers.parse('允許來源為 "{origin}"'))
def bot_allowed_origin(context, origin):
    context["bot"].widget_allowed_origins = [origin]


@given(parsers.parse("機器人 widget_keep_history 設為 {value}"))
def bot_keep_history(context, value):
    context["bot"].widget_keep_history = value.lower() == "true"


@when(parsers.parse('從來源 "{origin}" 發送 widget 訊息 "{message}"'))
def send_widget_message(context, mock_bot_repo, mock_send_message_use_case, origin, message):
    from src.interfaces.api.widget_router import validate_widget_bot, WidgetChatRequest

    short_code = context.get("short_code", "ab3Kx9")

    # Test validate_widget_bot
    try:
        bot = _run(validate_widget_bot(short_code, origin, mock_bot_repo))
        context["validated_bot"] = bot

        # Build and run the chat request
        req = WidgetChatRequest(message=message)
        conversation_id = req.conversation_id if bot.widget_keep_history else None

        # Collect stream events
        from src.application.agent.send_message_use_case import SendMessageCommand

        command = SendMessageCommand(
            tenant_id=bot.tenant_id,
            bot_id=bot.id.value,
            message=message,
            conversation_id=conversation_id,
        )

        events = []

        async def _collect():
            async for event in mock_send_message_use_case.execute_stream(command):
                events.append(event)
                # If keep_history is False, filter out conversation_id events
                if not bot.widget_keep_history and event.get("type") == "conversation_id":
                    events.pop()

        _run(_collect())
        context["stream_events"] = events
        context["error"] = None
    except Exception as exc:
        context["error"] = exc
        context["stream_events"] = []


@when(parsers.parse('從來源 "{origin}" 以 short_code "{sc}" 發送 widget 訊息 "{message}"'))
def send_widget_message_with_sc(context, mock_bot_repo, origin, sc, message):
    from src.interfaces.api.widget_router import validate_widget_bot

    mock_bot_repo.find_by_short_code = AsyncMock(return_value=None)

    try:
        _run(validate_widget_bot(sc, origin, mock_bot_repo))
        context["error"] = None
    except Exception as exc:
        context["error"] = exc


@then("應成功回傳串流回應")
def stream_success(context):
    assert context["error"] is None, f"Expected no error but got: {context['error']}"
    assert len(context["stream_events"]) > 0


@then(parsers.parse("應回傳錯誤碼 {code:d}"))
def error_code(context, code):
    from fastapi import HTTPException

    assert context["error"] is not None, "Expected an error"
    assert isinstance(context["error"], HTTPException)
    assert context["error"].status_code == code


@then(parsers.parse('錯誤訊息應包含 "{text}"'))
def error_message_contains(context, text):
    assert text in str(context["error"].detail)


@then("串流中應包含 conversation_id")
def stream_has_conversation_id(context):
    events = context["stream_events"]
    conv_events = [e for e in events if e.get("type") == "conversation_id"]
    assert len(conv_events) > 0, f"Expected conversation_id event, got: {events}"


@then("串流中不應包含 conversation_id")
def stream_no_conversation_id(context):
    events = context["stream_events"]
    conv_events = [e for e in events if e.get("type") == "conversation_id"]
    assert len(conv_events) == 0, f"Expected no conversation_id event, got: {events}"
