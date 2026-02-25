"""查詢供應商設定 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.platform.get_provider_setting_use_case import (
    GetProviderSettingUseCase,
)
from src.domain.platform.entity import ProviderSetting
from src.domain.platform.value_objects import (
    ProviderName,
    ProviderSettingId,
    ProviderType,
)
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/platform/get_provider_setting.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given(parsers.parse('系統中有 ID 為 "{setting_id}" 的供應商設定'))
def setting_exists(context, setting_id):
    setting = ProviderSetting(
        id=ProviderSettingId(value=setting_id),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="Test Provider",
        is_enabled=True,
        api_key_encrypted="enc:key",
    )
    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=setting)
    context["use_case"] = GetProviderSettingUseCase(
        provider_setting_repository=mock_repo
    )
    context["setting_id"] = setting_id


@given(parsers.parse('系統中沒有 ID 為 "{setting_id}" 的供應商設定'))
def setting_not_exists(context, setting_id):
    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=None)
    context["use_case"] = GetProviderSettingUseCase(
        provider_setting_repository=mock_repo
    )
    context["setting_id"] = setting_id


@when(parsers.parse('我查詢供應商設定 "{setting_id}"'))
def query_setting(context, setting_id):
    try:
        context["result"] = _run(context["use_case"].execute(setting_id))
        context["error"] = None
    except EntityNotFoundError as e:
        context["error"] = e


@then("應回傳該供應商設定")
def verify_setting(context):
    assert context["error"] is None
    assert context["result"].id.value == context["setting_id"]


@then("應拋出供應商設定不存在的錯誤")
def verify_not_found(context):
    assert context["error"] is not None
    assert isinstance(context["error"], EntityNotFoundError)
