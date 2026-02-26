import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.ratelimit.get_rate_limits_use_case import GetRateLimitsUseCase
from src.application.ratelimit.update_rate_limit_use_case import (
    InsufficientPermissionError,
    UpdateRateLimitCommand,
    UpdateRateLimitUseCase,
)
from src.domain.ratelimit.entity import RateLimitConfig
from src.domain.ratelimit.value_objects import EndpointGroup, RateLimitConfigId

scenarios("unit/ratelimit/rate_limit_config.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def mock_rl_repo():
    repo = AsyncMock()
    repo.find_defaults = AsyncMock(return_value=[])
    repo.find_all_by_tenant = AsyncMock(return_value=[])
    repo.find_by_tenant_and_group = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def get_use_case(mock_rl_repo):
    return GetRateLimitsUseCase(rate_limit_config_repository=mock_rl_repo)


@pytest.fixture
def update_use_case(mock_rl_repo):
    return UpdateRateLimitUseCase(rate_limit_config_repository=mock_rl_repo)


@pytest.fixture
def context():
    return {}


@given("系統有全域預設限流設定")
def global_defaults(mock_rl_repo):
    defaults = [
        RateLimitConfig(
            id=RateLimitConfigId(),
            tenant_id=None,
            endpoint_group=EndpointGroup.RAG,
            requests_per_minute=100,
            burst_size=120,
            per_user_requests_per_minute=50,
        ),
        RateLimitConfig(
            id=RateLimitConfigId(),
            tenant_id=None,
            endpoint_group=EndpointGroup.GENERAL,
            requests_per_minute=200,
            burst_size=250,
            per_user_requests_per_minute=100,
        ),
    ]
    mock_rl_repo.find_defaults = AsyncMock(return_value=defaults)


@given(parsers.parse('租戶 "{tenant_id}" 有自訂 "{group}" 端點群組設定'))
def tenant_override(mock_rl_repo, tenant_id, group):
    override = RateLimitConfig(
        id=RateLimitConfigId(),
        tenant_id=tenant_id,
        endpoint_group=EndpointGroup(group),
        requests_per_minute=500,
        burst_size=600,
        per_user_requests_per_minute=200,
    )
    mock_rl_repo.find_all_by_tenant = AsyncMock(return_value=[override])


@given(parsers.parse('目前使用者角色為 "{role}"'))
def current_role(context, role):
    context["role"] = role


@when(parsers.parse('我查詢租戶 "{tenant_id}" 的限流設定'))
def query_rate_limits(context, get_use_case, tenant_id):
    context["result"] = _run(get_use_case.execute(tenant_id))


@when(
    parsers.parse(
        '我更新租戶 "{tenant_id}" 的 "{group}" 端點群組限流為每分鐘 {rpm:d} 次'
    )
)
def update_rate_limit(context, update_use_case, tenant_id, group, rpm):
    command = UpdateRateLimitCommand(
        tenant_id=tenant_id,
        endpoint_group=group,
        requests_per_minute=rpm,
        burst_size=rpm + 50,
        caller_role=context.get("role", ""),
    )
    try:
        context["result"] = _run(update_use_case.execute(command))
        context["error"] = None
    except InsufficientPermissionError as e:
        context["result"] = None
        context["error"] = e


@then("應回傳合併後的設定")
def merged_configs(context):
    assert context["result"] is not None
    assert isinstance(context["result"], dict)


@then(parsers.parse('"{group}" 群組應使用租戶自訂值'))
def group_uses_tenant_value(context, group):
    cfg = context["result"][group]
    assert cfg.tenant_id is not None
    assert cfg.requests_per_minute == 500


@then(parsers.parse('"{group}" 群組應使用全域預設值'))
def group_uses_default(context, group):
    cfg = context["result"][group]
    assert cfg.tenant_id is None


@then("設定應成功更新")
def update_success(context):
    assert context["result"] is not None
    assert context["error"] is None


@then("repository 應被呼叫儲存")
def repo_save_called(mock_rl_repo):
    mock_rl_repo.save.assert_called_once()


@then("應拋出權限不足錯誤")
def permission_error(context):
    assert context["error"] is not None
    assert isinstance(context["error"], InsufficientPermissionError)
