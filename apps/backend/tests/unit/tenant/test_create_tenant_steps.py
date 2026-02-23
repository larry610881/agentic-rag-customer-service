"""建立租戶 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.tenant.create_tenant_use_case import (
    CreateTenantCommand,
    CreateTenantUseCase,
)
from src.domain.shared.exceptions import DuplicateEntityError
from src.domain.tenant.entity import Tenant
from src.domain.tenant.value_objects import TenantId

scenarios("unit/tenant/create_tenant.feature")


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
    repo = AsyncMock()
    repo.find_by_name = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def use_case(mock_tenant_repo):
    return CreateTenantUseCase(tenant_repository=mock_tenant_repo)


@given(parsers.parse('系統中尚未有名稱為 "{name}" 的租戶'))
def no_existing_tenant(mock_tenant_repo, name):
    mock_tenant_repo.find_by_name = AsyncMock(return_value=None)


@given(parsers.parse('系統中已有名稱為 "{name}" 的租戶'))
def existing_tenant(mock_tenant_repo, name):
    existing = Tenant(
        id=TenantId(),
        name=name,
        plan="starter",
    )
    mock_tenant_repo.find_by_name = AsyncMock(return_value=existing)


@when(parsers.parse('我以名稱 "{name}" 和方案 "{plan}" 建立租戶'))
def create_tenant(context, use_case, name, plan):
    command = CreateTenantCommand(name=name, plan=plan)
    try:
        context["result"] = _run(use_case.execute(command))
        context["error"] = None
    except DuplicateEntityError as e:
        context["result"] = None
        context["error"] = e


@then("租戶應成功建立")
def tenant_created(context):
    assert context["result"] is not None
    assert context["error"] is None


@then(parsers.parse('租戶名稱應為 "{name}"'))
def tenant_name_is(context, name):
    assert context["result"].name == name


@then(parsers.parse('租戶方案應為 "{plan}"'))
def tenant_plan_is(context, plan):
    assert context["result"].plan == plan


@then("應拋出重複租戶錯誤")
def duplicate_error_raised(context):
    assert context["error"] is not None
    assert isinstance(context["error"], DuplicateEntityError)
