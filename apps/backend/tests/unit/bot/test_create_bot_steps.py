"""建立機器人 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.bot.create_bot_use_case import (
    CreateBotCommand,
    CreateBotUseCase,
)
from src.domain.bot.repository import BotRepository

scenarios("unit/bot/create_bot.feature")


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


@given(parsers.parse('租戶 "{tenant_id}" 存在'))
def tenant_exists(context, tenant_id):
    context["tenant_id"] = tenant_id


@given(parsers.parse('知識庫 "{kb1}" 和 "{kb2}" 存在'))
def kbs_exist(context, kb1, kb2):
    context["kb_ids"] = [kb1, kb2]


@when(parsers.parse('建立機器人名稱 "{name}" 綁定知識庫 "{kb_ids_str}"'))
def create_bot_with_kbs(context, create_use_case, name, kb_ids_str):
    kb_ids = [k.strip() for k in kb_ids_str.split(",")]
    command = CreateBotCommand(
        tenant_id=context["tenant_id"],
        name=name,
        knowledge_base_ids=kb_ids,
    )
    context["result"] = _run(create_use_case.execute(command))


@when(parsers.parse('建立機器人名稱 "{name}" 不綁定知識庫'))
def create_bot_without_kbs(context, create_use_case, name):
    command = CreateBotCommand(
        tenant_id=context["tenant_id"],
        name=name,
    )
    context["result"] = _run(create_use_case.execute(command))


@when(
    parsers.parse(
        '建立機器人名稱 "{name}" 設定 temperature={temp:g} max_tokens={max_t:d}'
    )
)
def create_bot_with_llm_params(context, create_use_case, name, temp, max_t):
    command = CreateBotCommand(
        tenant_id=context["tenant_id"],
        name=name,
        temperature=temp,
        max_tokens=max_t,
    )
    context["result"] = _run(create_use_case.execute(command))


@then("機器人應成功建立")
def bot_created(context):
    assert context["result"] is not None
    assert context["result"].name != ""


@then(parsers.parse("機器人應綁定 {count:d} 個知識庫"))
def bot_kb_count(context, count):
    assert len(context["result"].knowledge_base_ids) == count


@then(parsers.parse("機器人預設 LLM 參數應為 temperature={temp:g} max_tokens={max_t:d}"))
def bot_default_llm_params(context, temp, max_t):
    params = context["result"].llm_params
    assert params.temperature == temp
    assert params.max_tokens == max_t


@then(parsers.parse("機器人的 temperature 應為 {temp:g}"))
def bot_temperature_is(context, temp):
    assert context["result"].llm_params.temperature == temp


@then(parsers.parse("機器人的 max_tokens 應為 {max_t:d}"))
def bot_max_tokens_is(context, max_t):
    assert context["result"].llm_params.max_tokens == max_t
