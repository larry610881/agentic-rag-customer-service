"""LINE Loading Animation BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.line.entity import LineTextMessageEvent

scenarios("unit/line/line_loading_animation.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {}


# --- 共用 steps ---


@given(
    parsers.parse(
        '載入動畫測試用戶 "{user_id}" 發送了文字訊息 "{text}"'
    )
)
def loading_user_sends_text(ctx, user_id, text):
    ctx["events"] = [
        LineTextMessageEvent(
            reply_token="token-loading",
            user_id=user_id,
            message_text=text,
            timestamp=1700000000000,
        )
    ]
    ctx["expected_user_id"] = user_id


@given("載入動畫測試 Agent 服務已準備回覆")
def loading_agent_ready(ctx):
    mock_agent = AsyncMock()
    ctx["mock_agent"] = mock_agent


# --- Scenario 1: 預設端點 ---


@when("系統透過預設端點處理載入動畫 Webhook 事件")
def process_default_loading_webhook(ctx):
    mock_line_service = AsyncMock()
    ctx["mock_line_service"] = mock_line_service

    call_order = []
    mock_line_service.show_loading.side_effect = (
        lambda *a, **kw: call_order.append("show_loading")
    )

    async def track_process(*a, **kw):
        call_order.append("process_message")
        return AgentResponse(answer="查詢結果")

    ctx["mock_agent"].process_message = AsyncMock(side_effect=track_process)
    ctx["call_order"] = call_order

    use_case = HandleWebhookUseCase(
        agent_service=ctx["mock_agent"],
        bot_repository=AsyncMock(),
        line_service_factory=MagicMock(),
        default_line_service=mock_line_service,
        default_tenant_id="tenant-001",
        default_kb_id="kb-001",
    )
    _run(use_case.execute(ctx["events"]))


@then(
    parsers.parse(
        '系統應對用戶 "{user_id}" 顯示載入動畫'
    )
)
def verify_loading_called_for_user(ctx, user_id):
    ctx["mock_line_service"].show_loading.assert_called_once_with(user_id)


@then("載入動畫應在 Agent 處理訊息之前被呼叫")
def verify_loading_order(ctx):
    assert ctx["call_order"] == ["show_loading", "process_message"]


# --- Scenario 2: Bot 端點 ---


@given(parsers.parse('載入動畫測試 Bot "{short_code}" 已設定 LINE Channel'))
def loading_bot_with_channel(ctx, short_code):
    bot = Bot(
        tenant_id="tenant-bot",
        name="Shop Bot",
        line_channel_secret="secret-loading",
        line_channel_access_token="token-loading",
        knowledge_base_ids=["kb-bot"],
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_short_code = AsyncMock(return_value=bot)
    ctx["mock_bot_repo"] = mock_bot_repo
    ctx["short_code"] = short_code


@given(
    parsers.parse(
        '載入動畫測試用戶 "{user_id}" 透過 Bot 發送了文字訊息 "{text}"'
    )
)
def loading_user_sends_via_bot(ctx, user_id, text):
    ctx["bot_body_text"] = (
        '{"events":[{"type":"message","replyToken":"token-loading",'
        f'"source":{{"userId":"{user_id}"}},'
        f'"message":{{"type":"text","text":"{text}"}},'
        '"timestamp":1700000000000}]}'
    )
    ctx["expected_user_id"] = user_id


@when("系統透過 Bot 端點處理載入動畫 Webhook 事件")
def process_bot_loading_webhook(ctx):
    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=True)
    ctx["mock_line_service"] = mock_line_service

    call_order = []
    mock_line_service.show_loading.side_effect = (
        lambda *a, **kw: call_order.append("show_loading")
    )

    async def track_process(*a, **kw):
        call_order.append("process_message")
        return AgentResponse(answer="查詢結果")

    ctx["mock_agent"].process_message = AsyncMock(side_effect=track_process)
    ctx["call_order"] = call_order

    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)

    use_case = HandleWebhookUseCase(
        agent_service=ctx["mock_agent"],
        bot_repository=ctx["mock_bot_repo"],
        line_service_factory=mock_factory,
    )
    _run(
        use_case.execute_for_bot(
            ctx["short_code"],
            ctx["bot_body_text"],
            "valid-sig",
        )
    )
