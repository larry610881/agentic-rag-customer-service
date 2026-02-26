"""LINE Webhook 簽名驗證時序 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot

scenarios("unit/line/line_webhook_security.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# --- Scenario: 無效簽名搭配 malformed JSON ---


@given(
    parsers.parse(
        'Bot "{bot_id}" 已設定 LINE Channel 且簽名驗證會失敗'
    )
)
def bot_with_failing_signature(context, bot_id):
    bot = Bot(
        tenant_id="tenant-sec",
        name="Security Bot",
        line_channel_secret="secret-sec",
        line_channel_access_token="token-sec",
        knowledge_base_ids=["kb-sec"],
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)

    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=False)
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)

    mock_agent = AsyncMock()
    context["mock_agent"] = mock_agent

    context["use_case"] = HandleWebhookUseCase(
        agent_service=mock_agent,
        bot_repository=mock_bot_repo,
        line_service_factory=mock_factory,
    )
    context["mock_line_service"] = mock_line_service


@when("系統收到無效簽名且 body 為 malformed JSON 的 Webhook")
def receive_malformed_json_with_bad_sig(context):
    # body 是 malformed JSON — 如果先 parse 會拋 JSONDecodeError
    body_text = "this is not valid json!!!"
    try:
        _run(
            context["use_case"].execute_for_bot(
                "bot-sec-001", body_text, "bad-sig"
            )
        )
        context["error"] = None
    except ValueError as e:
        context["error"] = e


@then("應拋出簽名驗證失敗錯誤")
def verify_signature_error(context):
    assert context["error"] is not None
    assert "Invalid LINE webhook signature" in str(context["error"])


@then("不應嘗試解析事件")
def verify_no_parsing(context):
    # Agent 不應被呼叫，因為驗簽就已失敗
    context["mock_agent"].process_message.assert_not_called()


# --- Scenario: 有效簽名搭配 malformed event ---


@given(
    parsers.parse(
        'Bot "{bot_id}" 已設定 LINE Channel 且簽名驗證會通過'
    )
)
def bot_with_passing_signature(context, bot_id):
    bot = Bot(
        tenant_id="tenant-sec",
        name="Security Bot",
        line_channel_secret="secret-sec",
        line_channel_access_token="token-sec",
        knowledge_base_ids=["kb-sec"],
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)

    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=True)
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)

    mock_agent = AsyncMock()
    context["mock_agent"] = mock_agent

    context["use_case"] = HandleWebhookUseCase(
        agent_service=mock_agent,
        bot_repository=mock_bot_repo,
        line_service_factory=mock_factory,
    )


@when("系統收到有效簽名但 events 格式異常的 Webhook")
def receive_malformed_events_with_good_sig(context):
    # 有效 JSON 但 events 結構不包含可解析的文字訊息
    body_text = '{"events":[{"type":"unknown","data":"corrupted"}]}'
    try:
        _run(
            context["use_case"].execute_for_bot(
                "bot-sec-002", body_text, "good-sig"
            )
        )
        context["error"] = None
    except Exception as e:
        context["error"] = e


@then("不應拋出錯誤")
def verify_no_error(context):
    assert context.get("error") is None


@then("不應呼叫 Agent 處理訊息")
def verify_agent_not_called(context):
    context["mock_agent"].process_message.assert_not_called()
