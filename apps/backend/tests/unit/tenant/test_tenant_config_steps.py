"""租戶設定管理 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.tenant.entity import Tenant

scenarios("unit/tenant/tenant_config.feature")


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


@given(parsers.parse('租戶 "{name}" 存在且無 Token 上限'))
def tenant_no_limit(context, name):
    tenant = Tenant(name=name, plan="starter", monthly_token_limit=None)
    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=tenant)
    mock_repo.save = AsyncMock()
    context["tenant"] = tenant
    context["mock_repo"] = mock_repo


@given(parsers.parse('租戶 "{name}" 有月 Token 上限 {limit:d}'))
def tenant_with_limit(context, name, limit):
    tenant = Tenant(name=name, plan="starter", monthly_token_limit=limit)
    mock_repo = AsyncMock()
    mock_repo.find_by_id = AsyncMock(return_value=tenant)
    mock_repo.save = AsyncMock()
    context["tenant"] = tenant
    context["mock_repo"] = mock_repo


# --- When ---


@when(parsers.parse("我設定月 Token 上限為 {limit:d}"))
def set_token_limit(context, limit):
    context["tenant"].monthly_token_limit = limit
    _run(context["mock_repo"].save(context["tenant"]))


@when("我將月 Token 上限設為 null")
def clear_token_limit(context):
    context["tenant"].monthly_token_limit = None
    _run(context["mock_repo"].save(context["tenant"]))


@when("我建立一個新的 Tenant entity")
def create_default_tenant(context):
    context["tenant"] = Tenant(name="新租戶")


# --- Then ---


@then(parsers.parse("租戶的 monthly_token_limit 應為 {limit:d}"))
def verify_limit(context, limit):
    assert context["tenant"].monthly_token_limit == limit


@then("租戶的 monthly_token_limit 應為 None")
def verify_none(context):
    assert context["tenant"].monthly_token_limit is None


@then("monthly_token_limit 應為 None")
def verify_default_none(context):
    assert context["tenant"].monthly_token_limit is None
