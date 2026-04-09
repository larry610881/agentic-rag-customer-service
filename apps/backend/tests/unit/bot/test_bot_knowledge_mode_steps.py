"""Bot Knowledge Mode BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.bot.create_bot_use_case import (
    CreateBotCommand,
    CreateBotUseCase,
)
from src.application.bot.update_bot_use_case import (
    UpdateBotCommand,
    UpdateBotUseCase,
)
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.shared.exceptions import ValidationError

scenarios("unit/bot/bot_knowledge_mode.feature")


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
    repo = AsyncMock(spec=BotRepository)
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def create_use_case(mock_bot_repo):
    return CreateBotUseCase(bot_repository=mock_bot_repo)


@pytest.fixture
def update_use_case(mock_bot_repo):
    return UpdateBotUseCase(bot_repository=mock_bot_repo)


@given(parsers.parse('租戶 "{tenant_id}" 存在'))
def tenant_exists(context, tenant_id):
    context["tenant_id"] = tenant_id


@given(parsers.parse('租戶 "{tenant_id}" 已存在一個 RAG 模式的機器人'))
def rag_bot_exists(context, mock_bot_repo, tenant_id):
    bot = Bot(
        id=BotId(value="bot-rag-001"),
        tenant_id=tenant_id,
        name="既有 RAG Bot",
        knowledge_mode="rag",
    )
    context["tenant_id"] = tenant_id
    context["bot"] = bot
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)


@given(parsers.parse('租戶 "{tenant_id}" 已存在一個 Wiki 模式的機器人'))
def wiki_bot_exists(context, mock_bot_repo, tenant_id):
    bot = Bot(
        id=BotId(value="bot-wiki-001"),
        tenant_id=tenant_id,
        name="既有 Wiki Bot",
        knowledge_mode="wiki",
    )
    context["tenant_id"] = tenant_id
    context["bot"] = bot
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)


@when(parsers.parse('建立機器人名稱 "{name}" 不指定知識模式'))
def create_bot_default_mode(context, create_use_case, name):
    command = CreateBotCommand(
        tenant_id=context["tenant_id"],
        name=name,
    )
    context["result"] = _run(create_use_case.execute(command))


@when(parsers.parse('建立機器人名稱 "{name}" 指定知識模式為 "{mode}"'))
def create_bot_with_mode(context, create_use_case, name, mode):
    command = CreateBotCommand(
        tenant_id=context["tenant_id"],
        name=name,
        knowledge_mode=mode,
    )
    context["result"] = _run(create_use_case.execute(command))


@when(parsers.parse('將機器人的知識模式更新為 "{mode}"'), target_fixture="result")
def update_bot_mode(context, update_use_case, mock_bot_repo, mode):
    # Make save return the updated bot so result carries the new mode
    async def _save(bot):
        return None
    mock_bot_repo.save = AsyncMock(side_effect=_save)
    command = UpdateBotCommand(
        bot_id=context["bot"].id.value,
        knowledge_mode=mode,
    )
    context["result"] = _run(update_use_case.execute(command))
    return context["result"]


@when(parsers.parse('只更新機器人的名稱為 "{name}"'), target_fixture="result")
def update_bot_name_only(context, update_use_case, name):
    command = UpdateBotCommand(
        bot_id=context["bot"].id.value,
        name=name,
    )
    context["result"] = _run(update_use_case.execute(command))
    return context["result"]


@when(parsers.parse('嘗試建立機器人指定知識模式為 "{mode}"'))
def try_create_bot_with_invalid_mode(context, create_use_case, mode):
    command = CreateBotCommand(
        tenant_id=context["tenant_id"],
        name="Invalid Mode Bot",
        knowledge_mode=mode,
    )
    try:
        context["result"] = _run(create_use_case.execute(command))
        context["error"] = None
    except ValidationError as exc:
        context["error"] = exc
        context["result"] = None


@then("機器人應成功建立")
def bot_created(context):
    assert context["result"] is not None
    assert context["result"].name != ""


@then(parsers.parse('機器人的知識模式應為 "{mode}"'))
def bot_knowledge_mode_is(context, mode):
    assert context["result"].knowledge_mode == mode


@then(parsers.parse('機器人的名稱應為 "{name}"'))
def bot_name_is(context, name):
    assert context["result"].name == name


@then("應回傳知識模式錯誤")
def verify_mode_error(context):
    assert context["error"] is not None
    assert isinstance(context["error"], ValidationError)
    assert "knowledge_mode" in str(context["error"]).lower()
