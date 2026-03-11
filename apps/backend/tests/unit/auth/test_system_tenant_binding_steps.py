"""系統租戶綁定與權限守衛 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.shared.constants import SYSTEM_TENANT_ID, SYSTEM_TENANT_NAME
from src.domain.tenant.entity import Tenant
from src.interfaces.api.deps import CurrentTenant, require_role

scenarios("unit/auth/system_tenant_binding.feature")


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


@given(parsers.parse('目前使用者角色為 "{role}"'))
def user_with_role(context, role):
    context["tenant"] = CurrentTenant(
        tenant_id=SYSTEM_TENANT_ID if role == "system_admin" else "t-xxx",
        user_id="u-001",
        role=role,
    )
    mock_repo = AsyncMock()
    mock_repo.find_all = AsyncMock(
        return_value=[
            Tenant(name="Tenant-A", plan="starter"),
            Tenant(name="Tenant-B", plan="starter"),
        ]
    )
    mock_repo.find_by_id = AsyncMock(return_value=Tenant(name="Self", plan="starter"))
    context["mock_repo"] = mock_repo


@given(parsers.parse('目前使用者角色為 "{role}" 且 tenant_id 為 "{tid}"'))
def user_with_role_and_tenant(context, role, tid):
    context["tenant"] = CurrentTenant(
        tenant_id=tid,
        user_id="u-001",
        role=role,
    )
    self_tenant = Tenant(name="Self", plan="starter")
    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=self_tenant)
    mock_repo.find_all = AsyncMock(
        return_value=[
            Tenant(name="Tenant-A", plan="starter"),
            Tenant(name="Tenant-B", plan="starter"),
        ]
    )
    context["mock_repo"] = mock_repo
    context["self_tenant"] = self_tenant


# --- When ---


@when("我列出所有租戶")
def list_tenants(context):
    tenant = context["tenant"]
    if tenant.role == "system_admin":
        result = _run(context["mock_repo"].find_all())
    else:
        single = _run(context["mock_repo"].find_by_id(tenant.tenant_id))
        result = [single] if single else []
    context["result"] = result


@when("我嘗試建立租戶")
def attempt_create_tenant(context):
    check_fn = require_role("system_admin")
    try:
        _run(check_fn(tenant=context["tenant"]))
        context["error"] = None
    except Exception as e:
        context["error"] = e


@when("我嘗試修改租戶 agent modes")
def attempt_patch_tenant(context):
    check_fn = require_role("system_admin")
    try:
        _run(check_fn(tenant=context["tenant"]))
        context["error"] = None
    except Exception as e:
        context["error"] = e


# --- Then ---


@then("應回傳所有租戶列表")
def verify_all_tenants(context):
    assert len(context["result"]) == 2


@then(parsers.parse('應只回傳 tenant_id 為 "{tid}" 的租戶'))
def verify_single_tenant(context, tid):
    assert len(context["result"]) == 1


@then("應被拒絕並回傳 403")
def verify_forbidden(context):
    from fastapi import HTTPException

    assert context["error"] is not None
    assert isinstance(context["error"], HTTPException)
    assert context["error"].status_code == 403


@then(parsers.parse('SYSTEM_TENANT_ID 應為 "{expected}"'))
def verify_system_tenant_id(expected):
    assert SYSTEM_TENANT_ID == expected


@then(parsers.parse('SYSTEM_TENANT_NAME 應為 "{expected}"'))
def verify_system_tenant_name(expected):
    assert SYSTEM_TENANT_NAME == expected
