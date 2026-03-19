"""BDD steps for System Admin Bot 404 Guard."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.bot.get_bot_use_case import GetBotUseCase
from src.domain.bot.entity import Bot
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/bot/system_admin_bot_lookup.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture
def context():
    return {}


# ── Given ──


@given("system_admin 已登入")
def setup_system_admin(context):
    context["role"] = "system_admin"
    # Default: bot not found
    bot_repo = AsyncMock()
    bot_repo.find_by_id = AsyncMock(return_value=None)
    context["bot_repo"] = bot_repo


@given(parsers.parse('機器人 "{bot_id}" 屬於租戶 "{tenant_id}"'))
def setup_existing_bot(context, bot_id, tenant_id):
    bot = Bot(tenant_id=tenant_id, name="Test Bot")
    context["bot_repo"].find_by_id = AsyncMock(return_value=bot)


# ── When ──


@when(parsers.parse('以 bot_id "{bot_id}" 發起對話'))
def lookup_bot(context, bot_id):
    use_case = GetBotUseCase(bot_repository=context["bot_repo"])
    try:
        bot = _run(use_case.execute(bot_id))
        context["error"] = None
        context["effective_tenant_id"] = bot.tenant_id
    except EntityNotFoundError as e:
        context["error"] = e
        context["effective_tenant_id"] = None


# ── Then ──


@then("應拋出 EntityNotFoundError")
def check_entity_not_found(context):
    assert isinstance(context["error"], EntityNotFoundError)


@then(parsers.parse('effective_tenant_id 應為 "{expected}"'))
def check_effective_tenant_id(context, expected):
    assert context["error"] is None, f"Unexpected error: {context['error']}"
    assert context["effective_tenant_id"] == expected
