"""Dynamic LLM Factory BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.platform.entity import ProviderSetting
from src.domain.platform.value_objects import (
    ModelConfig,
    ProviderName,
    ProviderSettingId,
    ProviderType,
)
from src.infrastructure.llm.dynamic_llm_factory import DynamicLLMServiceFactory

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


@when("工廠解析 LLM 服務")
def resolve_service(context, fallback_service):
    factory = DynamicLLMServiceFactory(
        provider_setting_repository=context["repo"],
        encryption_service=context["encryption"],
        fallback_service=fallback_service,
    )
    context["result"] = _run(factory.get_service())
    context["fallback"] = fallback_service


@then("應回傳 DB 來源的 LLM 服務")
def db_service_returned(context):
    assert context["result"] is not context["fallback"]


@then("應回傳 fallback 的 LLM 服務")
def fallback_service_returned(context):
    assert context["result"] is context["fallback"]
