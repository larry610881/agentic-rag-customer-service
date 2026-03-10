"""Dynamic LLM Factory BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.platform.entity import ProviderSetting
from src.domain.platform.value_objects import (
    ModelConfig,
    ProviderName,
    ProviderSettingId,
    ProviderType,
)
from src.infrastructure.llm.dynamic_llm_factory import DynamicLLMServiceFactory, _build_llm_service_from_config

scenarios("unit/platform/dynamic_llm_factory.feature")


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
def mock_repo():
    return AsyncMock()


@pytest.fixture
def mock_encryption():
    svc = MagicMock()
    svc.decrypt = lambda text: text.replace("enc:", "")
    return svc


@pytest.fixture
def fallback_service():
    svc = AsyncMock()
    svc._is_fallback = True
    return svc


@given("DB 中有一個啟用的 LLM 供應商設定")
def db_has_enabled_setting(context, mock_repo, mock_encryption):
    setting = ProviderSetting(
        id=ProviderSettingId(value="s1"),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI LLM",
        is_enabled=True,
        api_key_encrypted="enc:sk-test",
        base_url="https://api.openai.com/v1",
        models=[ModelConfig(model_id="gpt-4o", display_name="GPT-4o", is_default=True)],
    )
    mock_repo.find_all_by_type = AsyncMock(return_value=[setting])
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption


@given("DB 中沒有任何 LLM 供應商設定")
def db_has_no_settings(context, mock_repo, mock_encryption):
    mock_repo.find_all_by_type = AsyncMock(return_value=[])
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption


@given("DB 中的 LLM 供應商設定全部停用")
def db_all_disabled(context, mock_repo, mock_encryption):
    setting = ProviderSetting(
        id=ProviderSettingId(value="s1"),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI",
        is_enabled=False,
        api_key_encrypted="enc:key",
    )
    mock_repo.find_all_by_type = AsyncMock(return_value=[setting])
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption


@given("DB 中有一個啟用的 OpenAI 設定但 input_price 和 output_price 為 0")
def db_has_zero_price_setting(context, mock_repo, mock_encryption):
    setting = ProviderSetting(
        id=ProviderSettingId(value="s1"),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI",
        is_enabled=True,
        api_key_encrypted="enc:sk-test",
        base_url="https://api.openai.com/v1",
        models=[ModelConfig(model_id="gpt-5.1", display_name="GPT-5.1",
                            is_default=True, input_price=0.0, output_price=0.0)],
    )
    mock_repo.find_all_by_type = AsyncMock(return_value=[setting])
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption
    context["_capture_pricing"] = True


@given("DB 中有一個啟用的設定但模型不在 registry 中")
def db_has_unknown_model(context, mock_repo, mock_encryption):
    setting = ProviderSetting(
        id=ProviderSettingId(value="s1"),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI",
        is_enabled=True,
        api_key_encrypted="enc:sk-test",
        base_url="https://api.openai.com/v1",
        models=[ModelConfig(model_id="custom-xyz-model", display_name="Custom",
                            is_default=True, input_price=0.0, output_price=0.0)],
    )
    mock_repo.find_all_by_type = AsyncMock(return_value=[setting])
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption
    context["_capture_pricing"] = True


@when("工廠解析 LLM 服務")
def resolve_service(context, fallback_service):
    factory = DynamicLLMServiceFactory(
        provider_setting_repo_factory=lambda: context["repo"],
        encryption_service=context["encryption"],
        fallback_service=fallback_service,
    )
    if context.get("_capture_pricing"):
        captured = {}
        original_build = _build_llm_service_from_config

        def _capture_build(config):
            captured.update(config)
            return original_build(config)

        with patch(
            "src.infrastructure.llm.dynamic_llm_factory._build_llm_service_from_config",
            side_effect=_capture_build,
        ):
            context["result"] = _run(factory.get_service())
        context["captured_config"] = captured
    else:
        context["result"] = _run(factory.get_service())
    context["fallback"] = fallback_service


@then("應回傳 DB 來源的 LLM 服務")
def db_service_returned(context):
    assert context["result"] is not context["fallback"]


@then("應回傳 fallback 的 LLM 服務")
def fallback_service_returned(context):
    assert context["result"] is context["fallback"]


@then("服務的 pricing dict 應包含 registry 定價")
def verify_pricing_from_registry(context):
    config = context["captured_config"]
    assert "gpt-5.1" in config["pricing"]
    assert config["pricing"]["gpt-5.1"]["input"] == 1.25
    assert config["pricing"]["gpt-5.1"]["output"] == 10.0


@then("服務的 pricing dict 應為空")
def verify_pricing_empty(context):
    config = context["captured_config"]
    assert config["pricing"] == {}
