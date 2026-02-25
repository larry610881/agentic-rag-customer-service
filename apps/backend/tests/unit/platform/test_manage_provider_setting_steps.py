"""供應商設定管理 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.platform.create_provider_setting_use_case import (
    CreateProviderSettingCommand,
    CreateProviderSettingUseCase,
)
from src.application.platform.delete_provider_setting_use_case import (
    DeleteProviderSettingUseCase,
)
from src.application.platform.list_provider_settings_use_case import (
    ListProviderSettingsUseCase,
)
from src.application.platform.test_provider_connection_use_case import (
    CheckProviderConnectionUseCase,
)
from src.application.platform.update_provider_setting_use_case import (
    UpdateProviderSettingCommand,
    UpdateProviderSettingUseCase,
)
from src.domain.platform.entity import ProviderSetting
from src.domain.platform.value_objects import (
    ProviderName,
    ProviderSettingId,
    ProviderType,
)

scenarios("unit/platform/manage_provider_setting.feature")


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
    repo.delete = AsyncMock()
    repo.find_all_by_type = AsyncMock(return_value=[])
    repo.find_all = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_encryption():
    svc = AsyncMock()
    svc.encrypt = lambda text: f"enc:{text}"
    svc.decrypt = lambda text: text.replace("enc:", "")
    return svc


# --- Scenario: 建立時 API Key 應被加密 ---


@given("一個供應商設定建立用例")
def create_use_case_ready(context, mock_provider_repo, mock_encryption):
    context["use_case"] = CreateProviderSettingUseCase(
        provider_setting_repository=mock_provider_repo,
        encryption_service=mock_encryption,
    )
    context["repo"] = mock_provider_repo


@when(
    parsers.parse(
        '我以明文 API Key "{api_key}" 建立 "{ptype}" 類型的 "{pname}" 供應商'
    )
)
def create_with_key(context, api_key, ptype, pname):
    command = CreateProviderSettingCommand(
        provider_type=ptype,
        provider_name=pname,
        display_name="Test Provider",
        api_key=api_key,
    )
    context["result"] = _run(context["use_case"].execute(command))


@then("儲存的設定 API Key 應為加密值")
def saved_key_is_encrypted(context):
    assert context["result"].api_key_encrypted.startswith("enc:")


@then(parsers.parse('加密值不應等於 "{plain_key}"'))
def encrypted_not_plain(context, plain_key):
    assert context["result"].api_key_encrypted != plain_key


# --- Scenario: 更新 API Key 應重新加密 ---


@given(parsers.parse('一個已存在的供應商設定，ID 為 "{setting_id}"'))
def existing_setting(context, mock_provider_repo, mock_encryption, setting_id):
    existing = ProviderSetting(
        id=ProviderSettingId(value=setting_id),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="Existing",
        is_enabled=True,
        api_key_encrypted="enc:old-key",
    )
    mock_provider_repo.find_by_id = AsyncMock(return_value=existing)
    context["repo"] = mock_provider_repo
    context["encryption"] = mock_encryption


@when(parsers.parse('我更新設定 "{setting_id}" 的 API Key 為 "{new_key}"'))
def update_api_key(context, setting_id, new_key):
    use_case = UpdateProviderSettingUseCase(
        provider_setting_repository=context["repo"],
        encryption_service=context["encryption"],
    )
    command = UpdateProviderSettingCommand(
        setting_id=setting_id,
        api_key=new_key,
    )
    context["result"] = _run(use_case.execute(command))


@then("儲存的設定 API Key 應為新的加密值")
def new_encrypted_key(context):
    assert context["result"].api_key_encrypted == "enc:sk-new-key"


# --- Scenario: 列出所有 LLM 供應商 ---


@given(
    parsers.parse("系統中有 {llm_count:d} 個 LLM 供應商和 {emb_count:d} 個 Embedding 供應商")
)
def setup_providers(context, mock_provider_repo, llm_count, emb_count):
    llm_settings = [
        ProviderSetting(
            id=ProviderSettingId(),
            provider_type=ProviderType.LLM,
            provider_name=ProviderName.OPENAI,
            display_name=f"LLM-{i}",
        )
        for i in range(llm_count)
    ]
    mock_provider_repo.find_all_by_type = AsyncMock(return_value=llm_settings)
    context["repo"] = mock_provider_repo


@when(parsers.parse('我列出所有 "{ptype}" 類型的供應商'))
def list_by_type(context, ptype):
    use_case = ListProviderSettingsUseCase(
        provider_setting_repository=context["repo"],
    )
    context["list_result"] = _run(use_case.execute(provider_type=ptype))


@then(parsers.parse("應回傳 {count:d} 個供應商設定"))
def check_list_count(context, count):
    assert len(context["list_result"]) == count


# --- Scenario: 刪除供應商 ---


@when(parsers.parse('我刪除設定 "{setting_id}"'))
def delete_setting(context, setting_id):
    use_case = DeleteProviderSettingUseCase(
        provider_setting_repository=context["repo"],
    )
    _run(use_case.execute(setting_id))
    context["deleted"] = True


@then("刪除操作應成功")
def delete_succeeded(context):
    assert context["deleted"] is True
    context["repo"].delete.assert_called_once()


# --- Scenario: 測試供應商連線 ---


@given(parsers.parse('一個已存在的 fake 供應商設定，ID 為 "{setting_id}"'))
def fake_provider_setting(context, mock_provider_repo, mock_encryption, setting_id):
    setting = ProviderSetting(
        id=ProviderSettingId(value=setting_id),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.FAKE,
        display_name="Fake",
        is_enabled=True,
        api_key_encrypted="enc:fake-key",
    )
    mock_provider_repo.find_by_id = AsyncMock(return_value=setting)
    context["repo"] = mock_provider_repo
    context["encryption"] = mock_encryption


@when(parsers.parse('我測試設定 "{setting_id}" 的連線'))
def do_test_connection(context, setting_id):
    use_case = CheckProviderConnectionUseCase(
        provider_setting_repository=context["repo"],
        encryption_service=context["encryption"],
    )
    context["test_result"] = _run(use_case.execute(setting_id))


@then("連線測試結果應為成功")
def connection_success(context):
    assert context["test_result"].success is True
