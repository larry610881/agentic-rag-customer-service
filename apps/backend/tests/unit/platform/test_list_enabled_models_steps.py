"""BDD steps for listing enabled models."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.platform.list_enabled_models_use_case import (
    ListEnabledModelsUseCase,
)
from src.domain.platform.entity import ProviderSetting
from src.domain.platform.value_objects import (
    ModelConfig,
    ProviderName,
    ProviderSettingId,
    ProviderType,
)

scenarios("unit/platform/list_enabled_models.feature")


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
def mock_provider_repo():
    repo = AsyncMock()
    repo.find_all_by_type = AsyncMock(return_value=[])
    return repo


# --- Scenario 1: mixed enabled/disabled ---


@given(
    '有一個啟用的 "openai" LLM 供應商包含 3 個模型且其中 1 個已停用',
    target_fixture="context",
)
def openai_with_disabled_model(mock_provider_repo):
    openai_setting = ProviderSetting(
        id=ProviderSettingId(value="s1"),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI",
        is_enabled=True,
        models=[
            ModelConfig(
                model_id="gpt-5",
                display_name="GPT-5",
                is_enabled=True,
                price="$1.25/$10",
            ),
            ModelConfig(
                model_id="gpt-5-mini",
                display_name="GPT-5 Mini",
                is_enabled=True,
                price="$0.25/$2",
            ),
            ModelConfig(
                model_id="gpt-4.1",
                display_name="GPT-4.1",
                is_enabled=False,
                price="$2/$8",
            ),
        ],
    )
    return {"repo": mock_provider_repo, "settings": [openai_setting]}


@given('有一個停用的 "anthropic" LLM 供應商')
def anthropic_disabled(context, mock_provider_repo):
    anthropic_setting = ProviderSetting(
        id=ProviderSettingId(value="s2"),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.ANTHROPIC,
        display_name="Anthropic",
        is_enabled=False,
        models=[
            ModelConfig(
                model_id="claude-sonnet-4-6",
                display_name="Claude Sonnet 4.6",
                is_enabled=True,
            ),
        ],
    )
    context["settings"].append(anthropic_setting)
    mock_provider_repo.find_all_by_type = AsyncMock(
        return_value=context["settings"]
    )


@when("我查詢已啟用的模型列表", target_fixture="result")
def query_enabled_models(context):
    uc = ListEnabledModelsUseCase(
        provider_setting_repository=context["repo"],
    )
    return _run(uc.execute())


@then("應回傳 2 個模型")
def verify_count(result):
    assert len(result) == 2


@then('所有模型都來自 "openai"')
def verify_provider(result):
    for m in result:
        assert m.provider_name == "openai"


# --- Scenario 2: no enabled providers ---


@given("沒有任何啟用的 LLM 供應商", target_fixture="context")
def no_enabled_providers(mock_provider_repo):
    mock_provider_repo.find_all_by_type = AsyncMock(return_value=[])
    return {"repo": mock_provider_repo}


@then("應回傳空列表")
def verify_empty(result):
    assert result == []
