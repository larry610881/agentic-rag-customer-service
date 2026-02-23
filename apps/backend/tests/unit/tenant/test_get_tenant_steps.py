"""查詢租戶 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.tenant.get_tenant_use_case import GetTenantUseCase
from src.domain.shared.exceptions import EntityNotFoundError
from src.domain.tenant.entity import Tenant
from src.domain.tenant.value_objects import TenantId

scenarios("unit/tenant/get_tenant.feature")


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
def mock_tenant_repo():
    return AsyncMock()


@pytest.fixture
def use_case(mock_tenant_repo):
    return GetTenantUseCase(tenant_repository=mock_tenant_repo)


@given(parsers.parse('系統中已存在 ID 為 "{tenant_id}" 的租戶 "{name}"'))
def tenant_exists(mock_tenant_repo, tenant_id, name):
    tenant = Tenant(
        id=TenantId(value=tenant_id),
        name=name,
        plan="professional",
    )
    mock_tenant_repo.find_by_id = AsyncMock(return_value=tenant)


@given(parsers.parse('系統中不存在 ID 為 "{tenant_id}" 的租戶'))
def tenant_not_exists(mock_tenant_repo, tenant_id):
    mock_tenant_repo.find_by_id = AsyncMock(return_value=None)


@when(parsers.parse('我以 ID "{tenant_id}" 查詢租戶'))
def get_tenant(context, use_case, tenant_id):
    try:
        context["result"] = _run(use_case.execute(tenant_id))
        context["error"] = None
    except EntityNotFoundError as e:
        context["result"] = None
        context["error"] = e


@then("應回傳租戶資訊")
def tenant_returned(context):
    assert context["result"] is not None
    assert context["error"] is None


@then(parsers.parse('回傳的租戶名稱應為 "{name}"'))
def returned_tenant_name_is(context, name):
    assert context["result"].name == name


@then("應拋出租戶不存在錯誤")
def not_found_error_raised(context):
    assert context["error"] is not None
    assert isinstance(context["error"], EntityNotFoundError)
