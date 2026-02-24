"""管理機器人 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.bot.delete_bot_use_case import DeleteBotUseCase
from src.application.bot.get_bot_use_case import GetBotUseCase
from src.application.bot.list_bots_use_case import ListBotsUseCase
from src.application.bot.update_bot_use_case import UpdateBotCommand, UpdateBotUseCase
from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/bot/manage_bot.feature")


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
def existing_bot():
    return Bot(
        id=BotId("bot-001"),
        tenant_id="t-001",
        name="客服 Bot",
        description="測試用機器人",
        is_active=True,
        system_prompt="",
        knowledge_base_ids=["kb-001"],
        llm_params=BotLLMParams(),
    )


@pytest.fixture
def mock_bot_repo(existing_bot):
    repo = AsyncMock(spec=BotRepository)
    repo.find_by_id = AsyncMock(return_value=existing_bot)
    repo.find_all_by_tenant = AsyncMock(return_value=[existing_bot])
    repo.save = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def update_use_case(mock_bot_repo):
    return UpdateBotUseCase(bot_repository=mock_bot_repo)


@pytest.fixture
def delete_use_case(mock_bot_repo):
    return DeleteBotUseCase(bot_repository=mock_bot_repo)


@pytest.fixture
def get_use_case(mock_bot_repo):
    return GetBotUseCase(bot_repository=mock_bot_repo)


@pytest.fixture
def list_use_case(mock_bot_repo):
    return ListBotsUseCase(bot_repository=mock_bot_repo)


@given(parsers.parse('租戶 "{tenant_id}" 有一個機器人 "{bot_name}"'))
def tenant_has_bot(context, existing_bot, tenant_id, bot_name):
    context["bot"] = existing_bot
    context["bot_id"] = existing_bot.id.value


@when(parsers.parse("更新機器人的 temperature 為 {temp:g}"))
def update_temperature(context, update_use_case, temp):
    command = UpdateBotCommand(
        bot_id=context["bot_id"],
        temperature=temp,
    )
    context["result"] = _run(update_use_case.execute(command))


@when(parsers.parse('更新機器人名稱為 "{name}"'))
def update_name(context, update_use_case, name):
    command = UpdateBotCommand(
        bot_id=context["bot_id"],
        name=name,
    )
    context["result"] = _run(update_use_case.execute(command))


@when("刪除機器人")
def delete_bot(context, delete_use_case):
    _run(delete_use_case.execute(context["bot_id"]))
    context["deleted"] = True


@when(parsers.parse('刪除機器人 "{bot_id}"'))
def delete_bot_by_id(context, mock_bot_repo, delete_use_case, bot_id):
    mock_bot_repo.find_by_id = AsyncMock(return_value=None)
    try:
        _run(delete_use_case.execute(bot_id))
    except EntityNotFoundError as e:
        context["error"] = e


@when("取得機器人詳情")
def get_bot_detail(context, get_use_case):
    context["result"] = _run(get_use_case.execute(context["bot_id"]))


@when(parsers.parse('列出租戶 "{tenant_id}" 的機器人'))
def list_bots(context, list_use_case, tenant_id):
    context["result_list"] = _run(list_use_case.execute(tenant_id))


@then(parsers.parse("機器人的 temperature 應為 {temp:g}"))
def verify_temperature(context, temp):
    assert context["result"].llm_params.temperature == temp


@then(parsers.parse('機器人名稱應為 "{name}"'))
def verify_name(context, name):
    assert context["result"].name == name


@then("機器人應從資料庫移除")
def verify_deleted(context, mock_bot_repo):
    mock_bot_repo.delete.assert_called_once()


@then("應拋出 EntityNotFoundError")
def verify_entity_not_found(context):
    assert isinstance(context["error"], EntityNotFoundError)


@then("應回傳機器人資訊")
def verify_bot_info(context):
    assert context["result"] is not None


@then(parsers.parse("應回傳 {count:d} 個機器人"))
def verify_bot_count(context, count):
    assert len(context["result_list"]) == count
