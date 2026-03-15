"""身份解析 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.memory.resolve_identity_use_case import (
    ResolveIdentityCommand,
    ResolveIdentityUseCase,
)
from src.domain.memory.entity import VisitorIdentity, VisitorProfile
from src.domain.memory.repository import VisitorProfileRepository
from src.domain.memory.value_objects import (
    VisitorIdentityId,
    VisitorProfileId,
)

scenarios("unit/memory/resolve_identity.feature")


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
def mock_profile_repo():
    repo = AsyncMock(spec=VisitorProfileRepository)
    repo.find_identity = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    repo.save_identity = AsyncMock()
    return repo


@pytest.fixture
def use_case(mock_profile_repo):
    return ResolveIdentityUseCase(
        visitor_profile_repository=mock_profile_repo
    )


# --- Given ---


@given(parsers.parse('租戶 "{tenant_id}" 沒有任何訪客資料'))
def no_visitor_data(context, mock_profile_repo, tenant_id):
    context["tenant_id"] = tenant_id
    mock_profile_repo.find_identity.return_value = None


@given(parsers.parse('租戶 "{tenant_id}" 已有 Widget 訪客 "{ext_id}" 的 Profile'))
def existing_widget_visitor(context, mock_profile_repo, tenant_id, ext_id):
    context["tenant_id"] = tenant_id
    existing_identity = VisitorIdentity(
        id=VisitorIdentityId(),
        profile_id="existing-profile-id",
        tenant_id=tenant_id,
        source="widget",
        external_id=ext_id,
    )
    context["existing_profile_id"] = "existing-profile-id"

    async def find_identity_side_effect(**kwargs):
        if (
            kwargs.get("tenant_id") == tenant_id
            and kwargs.get("source") == "widget"
            and kwargs.get("external_id") == ext_id
        ):
            return existing_identity
        return None

    mock_profile_repo.find_identity = find_identity_side_effect


# --- When ---


@when(parsers.parse('Widget 訪客 "{ext_id}" 發送訊息'))
def widget_visitor_sends(context, use_case, ext_id):
    tenant_id = context.get("tenant_id", "t-001")
    command = ResolveIdentityCommand(
        tenant_id=tenant_id,
        source="widget",
        external_id=ext_id,
    )
    context["result"] = _run(use_case.execute(command))
    context["last_ext_id"] = ext_id


@when(parsers.parse('LINE 用戶 "{ext_id}" 發送訊息'))
def line_user_sends(context, use_case, ext_id):
    tenant_id = context.get("tenant_id", "t-001")
    command = ResolveIdentityCommand(
        tenant_id=tenant_id,
        source="line",
        external_id=ext_id,
    )
    context["result_2"] = _run(use_case.execute(command))


@when(parsers.parse('租戶 "{tenant_id}" 的 Widget 訪客 "{ext_id}" 發送訊息'))
def other_tenant_visitor(context, use_case, tenant_id, ext_id):
    command = ResolveIdentityCommand(
        tenant_id=tenant_id,
        source="widget",
        external_id=ext_id,
    )
    context["result_2"] = _run(use_case.execute(command))
    context["tenant_id_2"] = tenant_id


# --- Then ---


@then("應建立新的 VisitorProfile")
def should_create_profile(context, mock_profile_repo):
    mock_profile_repo.save.assert_called()


@then(parsers.parse('應建立 VisitorIdentity source 為 "{source}"'))
def should_create_identity(context, mock_profile_repo, source):
    mock_profile_repo.save_identity.assert_called()
    call_args = mock_profile_repo.save_identity.call_args
    identity = call_args[0][0] if call_args[0] else call_args[1].get("identity")
    assert identity.source == source


@then("應回傳既有的 profile_id")
def should_return_existing(context):
    assert context["result"] == "existing-profile-id"


@then("不應建立新的 Profile")
def should_not_create(context, mock_profile_repo):
    mock_profile_repo.save.assert_not_called()


@then("兩個 Profile 的 id 不同")
def profiles_different_id(context):
    first_id = context.get("result", context.get("existing_profile_id"))
    second_id = context.get("result_2")
    assert first_id != second_id


@then("兩個 Profile 的 tenant_id 不同")
def profiles_different_tenant(context):
    assert context["tenant_id"] != context.get("tenant_id_2")
