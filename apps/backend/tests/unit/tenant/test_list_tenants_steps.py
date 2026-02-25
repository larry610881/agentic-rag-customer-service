"""列出租戶 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.tenant.list_tenants_use_case import ListTenantsUseCase
from src.domain.tenant.entity import Tenant

scenarios("unit/tenant/list_tenants.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given(parsers.parse("系統中有 {count:d} 個租戶"))
def tenants_exist(context, count):
    tenants = [
        Tenant(name=f"Tenant-{i}", plan="starter") for i in range(count)
    ]
    mock_repo = AsyncMock()
    mock_repo.find_all = AsyncMock(return_value=tenants)
    context["use_case"] = ListTenantsUseCase(tenant_repository=mock_repo)
    context["expected_count"] = count


@when("我列出所有租戶")
def list_tenants(context):
    context["result"] = _run(context["use_case"].execute())


@then(parsers.parse("應回傳 {count:d} 個租戶"))
def verify_count(context, count):
    assert len(context["result"]) == count
