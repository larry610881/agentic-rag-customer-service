"""BDD steps for bot model selection."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.bot.create_bot_use_case import CreateBotCommand, CreateBotUseCase
from src.application.bot.update_bot_use_case import UpdateBotCommand, UpdateBotUseCase
from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId

scenarios("unit/bot/bot_model_selection.feature")


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
    repo.find_by_id = AsyncMock(return_value=None)
    return repo


# --- Scenario 1: Create bot with LLM provider/model ---


@given(
    '一個新機器人的建立請求包含 llm_provider "openai" 和 llm_model "gpt-5-mini"',
    target_fixture="context",
)
def create_request(mock_bot_repo):
    return {
        "repo": mock_bot_repo,
        "command": CreateBotCommand(
            tenant_id="t1",
            name="Test Bot",
            llm_provider="openai",
            llm_model="gpt-5-mini",
        ),
    }


@when("我執行建立機器人用例", target_fixture="result")
def execute_create(context):
    uc = CreateBotUseCase(bot_repository=context["repo"])
    return _run(uc.execute(context["command"]))


@then('機器人的 llm_provider 應為 "openai"')
def verify_provider_openai(result):
    assert result.llm_provider == "openai"


@then('機器人的 llm_model 應為 "gpt-5-mini"')
def verify_model_gpt5mini(result):
    assert result.llm_model == "gpt-5-mini"


# --- Scenario 2: Update bot LLM model ---


@given('已存在一個機器人使用 "openai" 的 "gpt-5"', target_fixture="context")
def existing_bot(mock_bot_repo):
    bot = Bot(
        id=BotId(value="bot-1"),
        tenant_id="t1",
        name="Test Bot",
        llm_provider="openai",
        llm_model="gpt-5",
        llm_params=BotLLMParams(),
    )
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)
    return {"repo": mock_bot_repo, "bot": bot}


@when(
    '我更新機器人的模型為 "anthropic" 的 "claude-sonnet-4-6"',
    target_fixture="result",
)
def update_model(context):
    uc = UpdateBotUseCase(bot_repository=context["repo"])
    # UpdateBotUseCase.execute() 回傳 (Bot, warm_up_status)；本測試只驗 Bot 欄位
    bot, _warm_up_status = _run(
        uc.execute(
            UpdateBotCommand(
                bot_id="bot-1",
                llm_provider="anthropic",
                llm_model="claude-sonnet-4-6",
            )
        )
    )
    return bot


@then('機器人的 llm_provider 應為 "anthropic"')
def verify_provider_anthropic(result):
    assert result.llm_provider == "anthropic"


@then('機器人的 llm_model 應為 "claude-sonnet-4-6"')
def verify_model_claude(result):
    assert result.llm_model == "claude-sonnet-4-6"
