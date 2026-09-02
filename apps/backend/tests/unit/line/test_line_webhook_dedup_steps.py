"""LINE Webhook 事件去重 BDD Step Definitions（Issue #58）"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.line.entity import LineTextMessageEvent
from src.infrastructure.line.redis_webhook_event_deduplicator import (
    RedisWebhookEventDeduplicator,
)

scenarios("unit/line/line_webhook_dedup.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


class _InMemoryDedup:
    """模擬 Redis SET NX：第一次認領成功，之後 False。"""

    def __init__(self):
        self.seen: set[str] = set()
        self.calls: list[str] = []

    async def claim(self, event_id: str) -> bool:
        self.calls.append(event_id)
        if event_id in self.seen:
            return False
        self.seen.add(event_id)
        return True


def _line_body(event_id, text, *, redelivery=False, include_id=True):
    event = {
        "type": "message",
        "replyToken": "token-001",
        "source": {"userId": "U-user"},
        "message": {"type": "text", "text": text},
        "timestamp": 1700000000000,
    }
    if include_id:
        event["webhookEventId"] = event_id
        event["deliveryContext"] = {"isRedelivery": redelivery}
    return json.dumps({"events": [event]})


def _postback_body(event_id, data):
    return json.dumps({"events": [{
        "type": "postback",
        "replyToken": "token-pb",
        "source": {"userId": "U-user"},
        "postback": {"data": data},
        "timestamp": 1700000000000,
        "webhookEventId": event_id,
        "deliveryContext": {"isRedelivery": False},
    }]})


def _setup_bot(context, with_dedup: bool):
    bot = Bot(
        tenant_id="tenant-abc",
        name="Shop A",
        line_channel_secret="secret-001",
        line_channel_access_token="token-001",
        knowledge_base_ids=["kb-default"],
    )
    repo = AsyncMock()
    repo.find_by_short_code = AsyncMock(return_value=bot)
    line_service = AsyncMock()
    line_service.verify_signature = AsyncMock(return_value=True)
    factory = MagicMock()
    factory.create = MagicMock(return_value=line_service)
    context["bot_repo"] = repo
    context["factory"] = factory
    context["line_service"] = line_service
    context["dedup"] = _InMemoryDedup() if with_dedup else None


def _build_use_case(context):
    agent = context.get("agent") or AsyncMock()
    uc = HandleWebhookUseCase(
        agent_service=agent,
        bot_repository=context["bot_repo"],
        line_service_factory=context["factory"],
        default_line_service=context["line_service"],
        default_tenant_id="tenant-abc",
        default_kb_id="kb-default",
        event_deduplicator=context["dedup"],
    )
    context["use_case"] = uc
    return uc


@given(parsers.parse(
    'Bot "{short_code}" 屬於租戶 "{tenant_id}" 且設定了 LINE Channel 與去重器'
))
def bot_with_dedup(context, short_code, tenant_id):
    context["short_code"] = short_code
    _setup_bot(context, with_dedup=True)


@given(parsers.parse(
    'Bot "{short_code}" 屬於租戶 "{tenant_id}" 且設定了 LINE Channel 但未注入去重器'
))
def bot_without_dedup(context, short_code, tenant_id):
    context["short_code"] = short_code
    _setup_bot(context, with_dedup=False)


@given(parsers.parse('Webhook body 含事件 "{event_id}" 文字 "{text}"'))
def body_with_event(context, event_id, text):
    context["body"] = _line_body(event_id, text)


@given(parsers.parse('另一個 Webhook body 含事件 "{event_id}" 文字 "{text}"'))
def second_body(context, event_id, text):
    context["body2"] = _line_body(event_id, text)


@given(parsers.parse('Webhook body 含未帶 webhookEventId 的文字事件 "{text}"'))
def body_without_id(context, text):
    context["body"] = _line_body("", text, include_id=False)


@given(parsers.parse('Webhook body 含 postback 事件 "{event_id}" 資料 "{data}"'))
def body_with_postback(context, event_id, data):
    context["body"] = _postback_body(event_id, data)


@given(parsers.parse(
    'Webhook body 含事件 "{event_id}" 文字 "{text}" '
    '且 deliveryContext.isRedelivery 為 true'
))
def body_redelivery(context, event_id, text):
    context["body"] = _line_body(event_id, text, redelivery=True)


@given(parsers.parse('Agent 服務已準備回覆 "{answer}"'))
def agent_ready(context, answer):
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer=answer))
    context["agent"] = agent


@given(parsers.parse('舊端點文字事件 "{event_id}" 文字 "{text}"'))
def legacy_events(context, event_id, text):
    context["events"] = [LineTextMessageEvent(
        reply_token="token-legacy",
        user_id="U-user",
        message_text=text,
        timestamp=1700000000000,
        webhook_event_id=event_id,
    )]


@when("系統兩次以相同 body 執行 prepare_and_reply")
def prepare_twice(context):
    uc = _build_use_case(context)
    context["ctx1"] = _run(uc.prepare_and_reply(
        context["short_code"], context["body"], "sig"))
    context["ctx2"] = _run(uc.prepare_and_reply(
        context["short_code"], context["body"], "sig"))


@when("系統依序以兩個 body 執行 prepare_and_reply")
def prepare_two_bodies(context):
    uc = _build_use_case(context)
    context["ctx1"] = _run(uc.prepare_and_reply(
        context["short_code"], context["body"], "sig"))
    context["ctx2"] = _run(uc.prepare_and_reply(
        context["short_code"], context["body2"], "sig"))


@when("系統以該 body 執行 prepare_and_reply")
def prepare_once(context):
    uc = _build_use_case(context)
    context["ctx1"] = _run(uc.prepare_and_reply(
        context["short_code"], context["body"], "sig"))


@when("系統兩次以相同 body 執行 execute_for_bot")
def execute_for_bot_twice(context):
    uc = _build_use_case(context)
    _run(uc.execute_for_bot(context["short_code"], context["body"], "sig"))
    _run(uc.execute_for_bot(context["short_code"], context["body"], "sig"))


@when("系統兩次以相同事件列表執行 execute")
def execute_twice(context):
    uc = _build_use_case(context)
    _run(uc.execute(context["events"]))
    _run(uc.execute(context["events"]))


@then(parsers.parse("第一次 context 應含 {n:d} 個文字事件"))
def first_ctx_events(context, n):
    assert len(context["ctx1"].events) == n


@then(parsers.parse("第二次 context 應含 {n:d} 個文字事件"))
def second_ctx_events(context, n):
    assert len(context["ctx2"].events) == n


@then(parsers.parse("兩次 context 都應含 {n:d} 個文字事件"))
def both_ctx_events(context, n):
    assert len(context["ctx1"].events) == n
    assert len(context["ctx2"].events) == n


@then(parsers.parse("第一次 context 應含 {n:d} 個 postback 事件"))
def first_ctx_postbacks(context, n):
    assert len(context["ctx1"].postback_events) == n


@then(parsers.parse("第二次 context 應含 {n:d} 個 postback 事件"))
def second_ctx_postbacks(context, n):
    assert len(context["ctx2"].postback_events) == n


@then("去重器不應被呼叫")
def dedup_not_called(context):
    assert context["dedup"].calls == []


@then("第一次 context 的文字事件 is_redelivery 應為 true")
def first_ctx_redelivery(context):
    assert context["ctx1"].events[0].is_redelivery is True


@then(parsers.parse("Agent 服務應只被呼叫 {n:d} 次"))
def agent_called_times(context, n):
    assert context["agent"].process_message.await_count == n


# ── Redis 實作 ──


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    return redis


@given("Redis SET NX 回傳成功")
def redis_set_ok(mock_redis):
    mock_redis.set = AsyncMock(return_value=True)


@given("Redis SET NX 回傳 None")
def redis_set_none(mock_redis):
    mock_redis.set = AsyncMock(return_value=None)


@given("Redis SET 拋出例外")
def redis_set_raises(mock_redis):
    mock_redis.set = AsyncMock(side_effect=ConnectionError("down"))


@when(parsers.parse('去重器認領事件 "{event_id}"'))
def dedup_claim(context, mock_redis, event_id):
    dedup = RedisWebhookEventDeduplicator(
        redis_client=mock_redis, ttl_seconds=3600
    )
    context["claim_result"] = _run(dedup.claim(event_id))


@then(parsers.parse("認領結果應為 {expected}"))
def claim_result(context, expected):
    assert context["claim_result"] is (expected == "true")


@then(parsers.parse('應以 key "{key}" 與 TTL {ttl:d} 秒執行 SET NX'))
def set_nx_called(mock_redis, key, ttl):
    args, kwargs = mock_redis.set.call_args
    assert args[0] == key
    assert kwargs.get("nx") is True
    assert kwargs.get("ex") == ttl
