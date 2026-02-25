"""供應商設定 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.platform.create_provider_setting_use_case import (
    CreateProviderSettingCommand,
    CreateProviderSettingUseCase,
)
from src.domain.platform.entity import ProviderSetting
from src.domain.platform.value_objects import (
    ProviderName,
    ProviderSettingId,
    ProviderType,
)
from src.domain.shared.exceptions import DuplicateEntityError

scenarios("unit/platform/provider_setting.feature")


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
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def mock_encryption_service():
    service = AsyncMock()
    service.encrypt = lambda text: f"encrypted:{text}"
    service.decrypt = lambda text: text.replace("encrypted:", "")
    return service


@pytest.fixture
def use_case(mock_provider_repo, mock_encryption_service):
    return CreateProviderSettingUseCase(
        provider_setting_repository=mock_provider_repo,
        encryption_service=mock_encryption_service,
    )


@given(
    parsers.parse('系統中尚未有 "{ptype}" 類型的 "{pname}" 供應商')
)
def no_existing_provider(mock_provider_repo, ptype, pname):
    mock_provider_repo.find_by_type_and_name = AsyncMock(return_value=None)


@given(
    parsers.parse('系統中已有 "{ptype}" 類型的 "{pname}" 供應商')
)
def existing_provider(mock_provider_repo, ptype, pname):
    existing = ProviderSetting(
        id=ProviderSettingId(),
        provider_type=ProviderType(ptype),
        provider_name=ProviderName(pname),
        display_name="Existing",
        is_enabled=True,
    )
    mock_provider_repo.find_by_type_and_name = AsyncMock(
        return_value=existing
    )


@given("一個已啟用的供應商設定")
def enabled_provider(context):
    setting = ProviderSetting(
        id=ProviderSettingId(),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI",
        is_enabled=True,
    )
    context["setting"] = setting


@when(
    parsers.parse(
        '我建立一個 "{ptype}" 類型的 "{pname}" 供應商設定，顯示名稱為 "{display_name}"'
    )
)
def create_provider_setting(context, use_case, ptype, pname, display_name):
    command = CreateProviderSettingCommand(
        provider_type=ptype,
        provider_name=pname,
        display_name=display_name,
        api_key="sk-test-key-123",
        base_url="",
        models=[],
        extra_config={},
    )
    try:
        context["result"] = _run(use_case.execute(command))
        context["error"] = None
    except DuplicateEntityError as e:
        context["result"] = None
        context["error"] = e


@when("我停用該供應商設定")
def disable_provider(context):
    context["setting"].disable()


@then("供應商設定應成功建立")
def provider_created(context):
    assert context["result"] is not None
    assert context["error"] is None


@then(parsers.parse('供應商類型應為 "{ptype}"'))
def provider_type_is(context, ptype):
    assert context["result"].provider_type.value == ptype


@then(parsers.parse('供應商名稱應為 "{pname}"'))
def provider_name_is(context, pname):
    assert context["result"].provider_name.value == pname


@then("供應商應為啟用狀態")
def provider_is_enabled(context):
    setting = context.get("result") or context.get("setting")
    assert setting.is_enabled is True


@then("供應商應為停用狀態")
def provider_is_disabled(context):
    assert context["setting"].is_enabled is False


@then("應拋出重複實體錯誤")
def duplicate_error_raised(context):
    assert context["error"] is not None
    assert isinstance(context["error"], DuplicateEntityError)
