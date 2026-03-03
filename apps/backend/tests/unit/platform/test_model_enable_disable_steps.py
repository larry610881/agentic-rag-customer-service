"""BDD steps for model enable/disable."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.platform.create_provider_setting_use_case import (
    CreateProviderSettingCommand,
    CreateProviderSettingUseCase,
)
from src.application.platform.update_provider_setting_use_case import (
    UpdateProviderSettingCommand,
    UpdateProviderSettingUseCase,
)
from src.domain.platform.entity import ProviderSetting
from src.domain.platform.model_registry import DEFAULT_MODELS
from src.domain.platform.value_objects import (
    ModelConfig,
    ProviderName,
    ProviderSettingId,
    ProviderType,
)

scenarios("unit/platform/model_enable_disable.feature")


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
    repo.find_by_type_and_name = AsyncMock(return_value=None)
    repo.find_by_id = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def mock_encryption():
    svc = AsyncMock()
    svc.encrypt = lambda text: f"enc:{text}"
    svc.decrypt = lambda text: text.replace("enc:", "")
    return svc


# --- Scenario 1 & 2: auto-fill / explicit models ---


@given('供應商 "openai" 的 "llm" 類型尚未建立設定', target_fixture="context")
def provider_not_exists(mock_provider_repo, mock_encryption):
    return {
        "repo": mock_provider_repo,
        "encryption": mock_encryption,
    }


@when("我建立供應商設定且不指定模型列表", target_fixture="result")
def create_without_models(context):
    uc = CreateProviderSettingUseCase(
        provider_setting_repository=context["repo"],
        encryption_service=context["encryption"],
    )
    return _run(
        uc.execute(
            CreateProviderSettingCommand(
                provider_type="llm",
                provider_name="openai",
                display_name="OpenAI",
                api_key="sk-test",
                models=[],
            )
        )
    )


@then("應自動從預設模型註冊表填充模型")
def verify_auto_fill(result):
    expected_count = len(DEFAULT_MODELS["openai"]["llm"])
    assert len(result.models) == expected_count


@then("所有模型預設為啟用狀態")
def verify_all_enabled(result):
    for m in result.models:
        assert m.is_enabled is True


# --- Scenario 2: explicit models ---


@when("我建立供應商設定並指定模型列表", target_fixture="result")
def create_with_models(context):
    uc = CreateProviderSettingUseCase(
        provider_setting_repository=context["repo"],
        encryption_service=context["encryption"],
    )
    return _run(
        uc.execute(
            CreateProviderSettingCommand(
                provider_type="llm",
                provider_name="openai",
                display_name="OpenAI",
                api_key="sk-test",
                models=[{"model_id": "custom-1", "display_name": "Custom Model"}],
            )
        )
    )


@then("應使用我指定的模型列表")
def verify_explicit_models(result):
    assert len(result.models) == 1
    assert result.models[0].model_id == "custom-1"


# --- Scenario 3: disable model ---


@given('已有啟用中的 "openai" LLM 供應商設定', target_fixture="context")
def existing_openai_setting(mock_provider_repo, mock_encryption):
    models = [
        ModelConfig(
            model_id=m["model_id"],
            display_name=m["display_name"],
            price=m.get("price", ""),
            is_enabled=True,
        )
        for m in DEFAULT_MODELS["openai"]["llm"]
    ]
    setting = ProviderSetting(
        id=ProviderSettingId(value="setting-1"),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI",
        is_enabled=True,
        models=models,
    )
    mock_provider_repo.find_by_id = AsyncMock(return_value=setting)
    return {
        "repo": mock_provider_repo,
        "encryption": mock_encryption,
        "setting": setting,
    }


@when('我更新模型列表將 "gpt-5-mini" 設為停用', target_fixture="result")
def disable_model(context):
    uc = UpdateProviderSettingUseCase(
        provider_setting_repository=context["repo"],
        encryption_service=context["encryption"],
    )
    updated_models = [
        {
            "model_id": m.model_id,
            "display_name": m.display_name,
            "is_default": m.is_default,
            "is_enabled": False if m.model_id == "gpt-5-mini" else m.is_enabled,
            "price": m.price,
            "description": m.description,
        }
        for m in context["setting"].models
    ]
    return _run(
        uc.execute(
            UpdateProviderSettingCommand(
                setting_id="setting-1",
                models=updated_models,
            )
        )
    )


@then('"gpt-5-mini" 的 is_enabled 應為 False')
def verify_disabled(result):
    target = next(m for m in result.models if m.model_id == "gpt-5-mini")
    assert target.is_enabled is False


@then("其他模型的 is_enabled 應維持 True")
def verify_others_enabled(result):
    for m in result.models:
        if m.model_id != "gpt-5-mini":
            assert m.is_enabled is True
