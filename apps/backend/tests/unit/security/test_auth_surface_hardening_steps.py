"""認證面加固 P1 BDD Step Definitions（Issue #67）

四個入口：/auth/register 角色授權、/auth/token 限 development、
/settings/providers 與 /mcp-servers 掛認證。router 層以 create_app +
Container provider override 驗證，不碰 DB。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from src.config import settings
from src.domain.auth.registration_policy import can_register
from src.domain.auth.value_objects import Role
from src.domain.platform.entity import McpServerRegistration
from src.domain.platform.value_objects import McpRegistryId
from src.domain.shared.constants import SYSTEM_TENANT_ID

scenarios("unit/security/auth_surface_hardening.feature")


def _tenant(value: str) -> str | None:
    if value == "SYSTEM":
        return SYSTEM_TENANT_ID
    if value in ("", "none", "-"):
        return None
    return value


# ---------------------------------------------------------------------------
# Domain policy
# ---------------------------------------------------------------------------


@pytest.fixture
def context():
    return {}


@given(parsers.parse('呼叫者角色 "{role}" 租戶 "{tenant}"'))
def actor(context, role, tenant):
    context["actor_role"] = None if role == "none" else role
    context["actor_tenant"] = _tenant(tenant)


@when(parsers.parse('檢查是否可建立角色 "{role}" 租戶 "{tenant}" 的使用者'))
def check_policy(context, role, tenant):
    context["allowed"] = can_register(
        actor_role=context["actor_role"],
        actor_tenant_id=context["actor_tenant"],
        target_role=Role(role),
        target_tenant_id=_tenant(tenant),
    )


@then(parsers.parse("授權結果應為 {allowed}"))
def policy_result(context, allowed):
    assert context["allowed"] is (allowed == "True")


# ---------------------------------------------------------------------------
# Router-level（create_app + provider override）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hardening_app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    application = create_app(skip_rate_limit=True)
    yield application
    mp.undo()


@pytest.fixture
def mocks(hardening_app):
    c = hardening_app.container
    register = AsyncMock()
    user = MagicMock()
    user.id.value = "u-new"
    user.email.value = "new@test.com"
    user.role.value = "user"
    user.tenant_id = "t1"
    register.execute.return_value = user

    list_providers = AsyncMock()
    list_providers.execute.return_value = []
    enabled_models = AsyncMock()
    enabled_models.execute.return_value = []
    repo = AsyncMock()
    repo.find_accessible.return_value = []
    repo.find_all.return_value = []
    repo.find_by_id.return_value = None

    overrides = {
        c.register_user_use_case: register,
        c.list_provider_settings_use_case: list_providers,
        c.list_enabled_models_use_case: enabled_models,
        c.mcp_server_repository: repo,
    }
    for provider, mock in overrides.items():
        provider.override(providers.Object(mock))
    yield {"register": register, "repo": repo}
    for provider in overrides:
        provider.reset_override()


@given("已啟動的測試應用")
def app_ready(context, hardening_app, mocks):
    context["client"] = TestClient(hardening_app)
    context["jwt"] = hardening_app.container.jwt_service()
    context["mocks"] = mocks
    context["headers"] = {}


@given(parsers.parse('以角色 "{role}" 租戶 "{tenant}" 的憑證'))
def with_credentials(context, role, tenant):
    tenant_id = _tenant(tenant)
    if role == "legacy":
        token = context["jwt"].create_tenant_token(tenant_id)
    else:
        token = context["jwt"].create_user_token(
            user_id=f"{role}-id", tenant_id=tenant_id, role=role
        )
    context["headers"] = {"Authorization": f"Bearer {token}"}


@given(parsers.parse('app_env 為 "{env}"'))
def set_app_env(context, monkeypatch, env):
    monkeypatch.setattr(settings, "app_env", env)


@given(
    parsers.parse(
        'MCP 伺服器 "{server_id}" scope "{scope}" 租戶 "{tenants}" 啟用 {enabled}'
    )
)
def mcp_server_exists(context, server_id, scope, tenants, enabled):
    server = McpServerRegistration(
        id=McpRegistryId(server_id),
        name="srv",
        scope=scope,
        tenant_ids=[t for t in tenants.split(",") if t and t != "-"],
        is_enabled=(enabled == "True"),
    )
    context["mocks"]["repo"].find_by_id.return_value = server


def _register(context, headers, role, tenant):
    context["resp"] = context["client"].post(
        "/api/v1/auth/register",
        json={
            "email": "new@test.com",
            "password": "pass1234",
            "role": role,
            "tenant_id": _tenant(tenant),
        },
        headers=headers,
    )


@when(parsers.parse('無憑證送出註冊角色 "{role}" 租戶 "{tenant}"'))
def register_anonymous(context, role, tenant):
    _register(context, {}, role, tenant)


@when(parsers.parse('送出註冊角色 "{role}" 租戶 "{tenant}"'))
def register_with_headers(context, role, tenant):
    _register(context, context["headers"], role, tenant)


@when(parsers.parse('送出 POST /api/v1/auth/token 租戶 "{tenant}"'))
def post_dev_token(context, tenant):
    context["resp"] = context["client"].post(
        "/api/v1/auth/token", json={"tenant_id": tenant}
    )


_BODIES = {
    "/api/v1/settings/providers": {
        "provider_type": "llm",
        "provider_name": "openai",
        "display_name": "OpenAI",
    },
    "/api/v1/mcp-servers": {"name": "srv"},
}


def _request(context, method, path, headers):
    body = None
    if method in ("POST", "PUT"):
        body = _BODIES.get(path.split("?")[0], {})
    context["resp"] = context["client"].request(
        method, path, json=body, headers=headers
    )


@when(parsers.parse('無憑證請求 "{method}" "{path}"'))
def request_anonymous(context, method, path):
    _request(context, method, path, {})


@when(parsers.parse('請求 "{method}" "{path}"'))
def request_with_headers(context, method, path):
    _request(context, method, path, context["headers"])


@then(parsers.parse("回應狀態碼為 {status:d}"))
def status_is(context, status):
    assert context["resp"].status_code == status, context["resp"].text


@then("註冊用例不應被呼叫")
def register_not_called(context):
    context["mocks"]["register"].execute.assert_not_awaited()


@then(parsers.parse('MCP 儲存庫應以租戶 "{tenant}" 查詢可用清單'))
def repo_find_accessible_with(context, tenant):
    context["mocks"]["repo"].find_accessible.assert_awaited_once_with(tenant)
    context["mocks"]["repo"].find_all.assert_not_awaited()


@then("MCP 儲存庫應查詢全部清單")
def repo_find_all(context):
    context["mocks"]["repo"].find_all.assert_awaited_once()
    context["mocks"]["repo"].find_accessible.assert_not_awaited()
