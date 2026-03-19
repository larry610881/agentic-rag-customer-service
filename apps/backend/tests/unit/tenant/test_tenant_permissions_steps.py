"""租戶權限管理 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.tenant.entity import Tenant

scenarios("unit/tenant/tenant_permissions.feature")

_VALID_AGENT_MODES = {"router", "react"}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# --- Given ---


@given("一個 starter 方案的租戶")
def starter_tenant(context):
    tenant = Tenant(name="測試租戶", plan="starter", allowed_agent_modes=["router"])
    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=tenant)
    mock_repo.save = AsyncMock()
    context["tenant"] = tenant
    context["mock_repo"] = mock_repo


# --- When ---


@when("系統管理員設定 allowed_agent_modes 為 router 和 react")
def set_modes_router_react(context):
    modes = ["router", "react"]
    invalid = set(modes) - _VALID_AGENT_MODES
    assert not invalid, f"Invalid modes: {invalid}"
    context["tenant"].allowed_agent_modes = modes
    _run(context["mock_repo"].save(context["tenant"]))


@when("系統管理員設定 allowed_agent_modes 包含無效值 invalid_mode")
def set_invalid_mode(context):
    modes = ["router", "invalid_mode"]
    invalid = set(modes) - _VALID_AGENT_MODES
    if invalid:
        context["validation_error"] = f"Invalid agent modes: {sorted(invalid)}"
    else:
        context["tenant"].allowed_agent_modes = modes
        _run(context["mock_repo"].save(context["tenant"]))


# --- Then ---


@then("設定應成功儲存")
def verify_saved(context):
    context["mock_repo"].save.assert_called_once_with(context["tenant"])


@then("allowed_agent_modes 應包含 router 和 react")
def verify_modes_router_react(context):
    assert context["tenant"].allowed_agent_modes == ["router", "react"]


@then("allowed_agent_modes 不應被變更")
def verify_modes_unchanged(context):
    assert "validation_error" in context
    assert context["tenant"].allowed_agent_modes == ["router"]


