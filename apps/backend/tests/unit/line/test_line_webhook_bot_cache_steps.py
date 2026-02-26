"""Bot 查詢 TTL 快取 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.infrastructure.cache.in_memory_cache_service import InMemoryCacheService

scenarios("unit/line/line_webhook_bot_cache.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _build_cached_use_case(context, bot_id, cache_ttl):
    bot = Bot(
        tenant_id="tenant-cache",
        name="Cache Bot",
        line_channel_secret="secret-cache",
        line_channel_access_token="token-cache",
        knowledge_base_ids=["kb-cache"],
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)

    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=True)
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)

    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="cached reply")
    )

    cache_service = InMemoryCacheService()

    context["use_case"] = HandleWebhookUseCase(
        agent_service=mock_agent,
        bot_repository=mock_bot_repo,
        line_service_factory=mock_factory,
        cache_service=cache_service,
        cache_ttl=cache_ttl,
    )
    context["mock_bot_repo"] = mock_bot_repo
    context["bot_id"] = bot_id


@given(parsers.parse('Bot "{bot_id}" 已設定且快取 TTL 為 60 秒'))
def bot_with_long_ttl(context, bot_id):
    _build_cached_use_case(context, bot_id, cache_ttl=60)


@given(parsers.parse('Bot "{bot_id}" 已設定且快取 TTL 為 0 秒'))
def bot_with_zero_ttl(context, bot_id):
    # TTL=0 means no cache (InMemoryCacheService will expire immediately)
    _build_cached_use_case(context, bot_id, cache_ttl=0)


@when("系統連續兩次處理同一 Bot ID 的 Webhook")
def process_webhook_twice(context):
    body_text = '{"events":[{"type":"message","replyToken":"tk-c","source":{"userId":"U-c"},"message":{"type":"text","text":"hi"},"timestamp":1}]}'
    for _ in range(2):
        _run(
            context["use_case"].execute_for_bot(
                context["bot_id"], body_text, "sig"
            )
        )


@then("Bot Repository 應只查詢一次")
def verify_single_db_call(context):
    assert context["mock_bot_repo"].find_by_id.call_count == 1


@then("Bot Repository 應查詢兩次")
def verify_double_db_call(context):
    assert context["mock_bot_repo"].find_by_id.call_count == 2
