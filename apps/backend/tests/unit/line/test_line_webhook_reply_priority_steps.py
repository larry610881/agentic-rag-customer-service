"""LINE Webhook 回覆優先於持久化 — BDD Steps（Issue #49）

延遲實測：回覆送出前的串行持久化（存對話 → 存 trace → 記 usage）
與同步 await 的 show_loading 合計 ~0.4–0.6s 純體感浪費。
此測試鎖定三個行為契約：
1. reply 先於 conversation save 送出
2. show_loading 不阻塞主流程
3. reply 失敗時對話仍持久化（durability 與重排前一致）
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot

scenarios("unit/line/line_webhook_reply_priority.feature")

BODY = (
    '{"events":[{"type":"message","replyToken":"token-rp-001",'
    '"source":{"userId":"U-rp-user"},'
    '"message":{"type":"text","text":"請問營業時間"},'
    '"timestamp":1700000000000}]}'
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given("一個綁定 LINE Channel 且掛載對話儲存的 Bot")
def bot_with_conversation_repo(context):
    bot = Bot(
        tenant_id="tenant-rp",
        name="LINE Reply Priority Bot",
        line_channel_secret="secret-rp",
        line_channel_access_token="token-rp",
        knowledge_base_ids=["kb-rp"],
    )
    call_order: list[str] = []
    context["call_order"] = call_order
    context["bot"] = bot

    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_short_code = AsyncMock(return_value=bot)
    context["mock_bot_repo"] = mock_bot_repo

    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=True)

    async def _reply(*args, **kwargs):
        call_order.append("reply")

    mock_line_service.reply_with_quick_reply = AsyncMock(side_effect=_reply)
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)
    context["mock_factory"] = mock_factory
    context["mock_line_service"] = mock_line_service

    mock_conv_repo = AsyncMock()
    mock_conv_repo.find_latest_by_visitor = AsyncMock(return_value=None)

    async def _save(*args, **kwargs):
        call_order.append("save")

    mock_conv_repo.save = AsyncMock(side_effect=_save)
    context["mock_conv_repo"] = mock_conv_repo


@given("Agent 服務已準備好回覆內容")
def agent_ready(context):
    call_order = context["call_order"]

    async def _process(*args, **kwargs):
        call_order.append("process_start")
        # 模擬 RAG + LLM 處理時間，讓背景 loading task 有機會完成
        await asyncio.sleep(0.1)
        return AgentResponse(answer="今日營業到晚上九點")

    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(side_effect=_process)
    context["mock_agent"] = mock_agent


@given("LINE 載入動畫 API 需要 1 秒才回應")
def slow_loading(context):
    call_order = context["call_order"]

    async def _slow_loading(*args, **kwargs):
        # 測試用縮短為 0.05s；契約是「主流程不等它」，時長無關
        await asyncio.sleep(0.05)
        call_order.append("loading_done")

    context["mock_line_service"].show_loading = AsyncMock(
        side_effect=_slow_loading
    )


@given("LINE 回覆 API 會拋出例外")
def reply_raises(context):
    context["mock_line_service"].reply_with_quick_reply = AsyncMock(
        side_effect=RuntimeError("LINE reply API down")
    )


def _build_and_run(context):
    use_case = HandleWebhookUseCase(
        agent_service=context["mock_agent"],
        bot_repository=context["mock_bot_repo"],
        line_service_factory=context["mock_factory"],
        conversation_repository=context["mock_conv_repo"],
    )
    return use_case.execute_for_bot("RP01", BODY, "valid-sig")


@when("系統處理一則 LINE 文字訊息事件")
def process_event(context):
    _run(_build_and_run(context))


@when("系統處理一則 LINE 文字訊息事件並容忍回覆失敗")
def process_event_tolerating_reply_failure(context):
    try:
        _run(_build_and_run(context))
    except RuntimeError:
        pass


@then("LINE 回覆應在對話持久化之前送出")
def reply_before_persist(context):
    call_order = context["call_order"]
    assert "reply" in call_order, f"reply 未送出: {call_order}"
    assert "save" in call_order, f"對話未持久化: {call_order}"
    assert call_order.index("reply") < call_order.index("save"), (
        f"reply 應先於 save，實際順序: {call_order}"
    )


@then("主流程不應等待載入動畫完成才開始處理")
def loading_not_blocking(context):
    call_order = context["call_order"]
    assert "process_start" in call_order, f"主流程未執行: {call_order}"
    assert "loading_done" in call_order, (
        f"loading 應在處理期間於背景完成: {call_order}"
    )
    assert call_order.index("process_start") < call_order.index(
        "loading_done"
    ), f"主流程應先於 loading 完成，實際順序: {call_order}"


@then("對話仍應被持久化")
def conversation_persisted(context):
    assert "save" in context["call_order"], (
        f"reply 失敗時對話應仍持久化: {context['call_order']}"
    )
