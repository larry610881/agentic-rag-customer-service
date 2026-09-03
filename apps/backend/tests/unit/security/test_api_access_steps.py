"""API 模式端點 BDD Step Definitions（Issue #67 P2）

router 層：create_app + Container override。api_key_repository 換成記憶體版，
API key 用例（建立/列出/撤銷/換票/驗票）走真實實作；聊天等下游用例 mock。
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.auth.api_key import (
    ApiKey,
    hash_client_secret,
    new_salt,
    secret_display_prefix,
)
from src.domain.auth.api_key_repository import ApiKeyRepository
from src.domain.shared.constants import SYSTEM_TENANT_ID
from src.infrastructure.auth.in_memory_token_stores import (
    InMemoryRefreshTokenStore,
    InMemoryTokenRevocationStore,
)

scenarios("unit/security/api_access.feature")

_K1_SECRET = "ark_dev_" + "k" * 32
_ALL_SCOPES = [
    "chat:send", "chat:stream", "chat:history:read", "feedback:write", "bots:read",
]


class FakeApiKeyRepo(ApiKeyRepository):
    def __init__(self) -> None:
        self.store: dict[str, ApiKey] = {}

    async def save(self, key: ApiKey) -> None:
        self.store[key.id] = key

    async def find_by_id(self, key_id: str) -> ApiKey | None:
        return self.store.get(key_id)

    async def list_by_tenant(self, tenant_id: str) -> list[ApiKey]:
        return [k for k in self.store.values() if k.tenant_id == tenant_id]

    async def list_all(self) -> list[ApiKey]:
        return list(self.store.values())

    async def touch_last_used(self, key_id: str, when: datetime) -> None:
        if key_id in self.store:
            self.store[key_id].last_used_at = when


def _tenant(value: str) -> str | None:
    if value == "SYSTEM":
        return SYSTEM_TENANT_ID
    return None if value in ("", "-", "none") else value


def _chat_result():
    return SimpleNamespace(
        answer="ok", conversation_id="c1", trace_id=None, trace_nodes=None,
        tool_calls=[], sources=[], contact=None, usage=None, message_id="m1",
        config_version_id=None, config_hash=None, guard_blocked=False,
        guard_rule_matched=None,
    )


def _feedback_result():
    return SimpleNamespace(
        id=SimpleNamespace(value="f1"), tenant_id="t1", conversation_id="c1",
        message_id="m1", user_id=None, channel=SimpleNamespace(value="web"),
        rating=SimpleNamespace(value="thumbs_up"), comment=None, tags=[],
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture(scope="module")
def api_app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    yield create_app(skip_rate_limit=True)
    mp.undo()


@pytest.fixture
def context():
    return {}


@given("已啟動的 API 存取測試應用")
def app_ready(context, api_app):
    c = api_app.container
    repo = FakeApiKeyRepo()
    salt = new_salt()
    repo.store["k1"] = ApiKey(
        id="k1", tenant_id="t1", name="k1", scopes=list(_ALL_SCOPES),
        secret_hash=hash_client_secret(_K1_SECRET, salt), secret_salt=salt,
        secret_prefix=secret_display_prefix(_K1_SECRET),
    )
    send = AsyncMock()
    send.execute.return_value = _chat_result()
    conv = AsyncMock()
    conv.execute.return_value = []
    conv.count.return_value = 0
    bots = AsyncMock()
    bots.execute.return_value = []
    bots.count.return_value = 0
    fb = AsyncMock()
    fb.execute.return_value = _feedback_result()
    overrides = {
        c.api_key_repository: repo,
        c.audit_recorder: AsyncMock(),
        c.send_message_use_case: send,
        c.record_usage_use_case: AsyncMock(),
        c.list_conversations_use_case: conv,
        c.list_bots_use_case: bots,
        c.submit_feedback_use_case: fb,
        c.token_revocation_store: InMemoryTokenRevocationStore(),
        c.refresh_token_store: InMemoryRefreshTokenStore(),
    }
    for provider, obj in overrides.items():
        provider.override(providers.Object(obj))
    context.update(
        client=TestClient(api_app), jwt=c.jwt_service(), repo=repo, headers={},
        overrides=overrides,
    )
    yield
    for provider in overrides:
        provider.reset_override()


@given(parsers.parse('持有 client "{client_id}" 的 api_access 票 scopes "{scopes}"'))
def api_token(context, client_id, scopes):
    token, _ = context["jwt"].create_api_access_token(
        client_id=client_id, tenant_id="t1", scopes=scopes.split(), bot_ids=[],
        version=1,
    )
    context["headers"] = {"Authorization": f"Bearer {token}"}


@given(parsers.parse(
    '持有 client "{client_id}" 的 api_access 票 scopes "{scopes}" bot_ids "{bot_ids}"'
))
def api_token_with_bots(context, client_id, scopes, bot_ids):
    ids = [] if bot_ids == "-" else bot_ids.split(",")
    token, _ = context["jwt"].create_api_access_token(
        client_id=client_id, tenant_id="t1", scopes=scopes.split(), bot_ids=ids,
        version=1,
    )
    context["headers"] = {"Authorization": f"Bearer {token}"}


@given(parsers.parse('client "{client_id}" 已被撤銷'))
def client_revoked(context, client_id):
    context["repo"].store[client_id].revoke()


@given(parsers.parse('持有租戶 "{tenant}" 的一般使用者票'))
def user_token(context, tenant):
    token = context["jwt"].create_user_token(
        user_id="u1", tenant_id=tenant, role="user"
    )
    context["headers"] = {"Authorization": f"Bearer {token}"}


@given(parsers.parse('持有租戶 "{tenant}" 角色 "{role}" 的人類票'))
def human_token(context, tenant, role):
    token = context["jwt"].create_user_token(
        user_id=f"{role}-id", tenant_id=_tenant(tenant), role=role
    )
    context["headers"] = {"Authorization": f"Bearer {token}"}


def _exchange(context, body):
    context["resp"] = context["client"].post("/api/v1/auth/token", json=body)


@when(parsers.parse('以 grant_type "{grant}" 換票'))
def exchange_grant(context, grant):
    _exchange(context, {"grant_type": grant, "client_id": "k1", "client_secret": "x"})


@when(parsers.parse('以 client "{client_id}" secret "{secret}" 換票'))
def exchange_bad(context, client_id, secret):
    _exchange(context, {
        "grant_type": "client_credentials", "client_id": client_id,
        "client_secret": secret,
    })


@when(parsers.parse('以 client "{client_id}" 正確 secret 換票'))
def exchange_ok(context, client_id):
    _exchange(context, {
        "grant_type": "client_credentials", "client_id": client_id,
        "client_secret": _K1_SECRET, "scope": "chat:send",
    })


@when(parsers.parse('以 client "{client_id}" 正確 secret 換票並要求 scope "{scope}"'))
def exchange_scope(context, client_id, scope):
    _exchange(context, {
        "grant_type": "client_credentials", "client_id": client_id,
        "client_secret": _K1_SECRET, "scope": scope,
    })


_BODIES = {
    "/api/v1/agent/chat": {"message": "hi"},
    "/api/v1/feedback": {
        "conversation_id": "c1", "message_id": "m1", "channel": "web",
        "rating": "thumbs_up",
    },
    "/api/v1/api-keys": {"name": "n", "scopes": ["chat:send"]},
}


@when(parsers.parse('以機器票請求 "{method}" "{path}"'))
def request_with_token(context, method, path):
    body = _BODIES.get(path) if method in ("POST", "PUT") else None
    context["resp"] = context["client"].request(
        method, path, json=body, headers=context["headers"]
    )


@when(parsers.parse('以機器票對 bot "{bot_id}" 送出聊天'))
def chat_with_bot(context, bot_id):
    body = {"message": "hi", "bot_id": _tenant(bot_id)}
    context["resp"] = context["client"].post(
        "/api/v1/agent/chat", json=body, headers=context["headers"]
    )


@when(parsers.parse('以人類票建立租戶 "{target}" 的 API key'))
def create_key(context, target):
    body = {"name": "看板", "scopes": ["chat:send"]}
    if _tenant(target):
        body["tenant_id"] = _tenant(target)
    context["resp"] = context["client"].post(
        "/api/v1/api-keys", json=body, headers=context["headers"]
    )


@when("以人類票列出 API key")
def list_keys(context):
    context["resp"] = context["client"].get(
        "/api/v1/api-keys", headers=context["headers"]
    )


@then(parsers.parse("API 回應狀態碼為 {status:d}"))
def status_is(context, status):
    assert context["resp"].status_code == status, context["resp"].text


@then(parsers.parse('API 回應 detail 為 "{detail}"'))
def detail_is(context, detail):
    assert context["resp"].json()["detail"] == detail


@then(parsers.parse('換票回應 token_type 為 "{ttype}" expires_in 為 {exp:d}'))
def token_shape(context, ttype, exp):
    body = context["resp"].json()
    assert body["token_type"] == ttype
    assert body["expires_in"] == exp
    assert body["scope"] == "chat:send"
    assert "refresh_token" not in body
    payload = context["jwt"].decode_token(body["access_token"])
    assert payload["type"] == "api_access" and payload["sub"] == "k1"


@then("建立回應含 client_secret")
def created_has_secret(context):
    body = context["resp"].json()
    assert body["client_secret"].startswith("ark_")
    assert body["secret_prefix"] == body["client_secret"][:12]
    context["created_id"] = body["id"]


@then("列表回應每筆都不含 client_secret")
def list_has_no_secret(context):
    body = context["resp"].json()
    assert any(k["id"] == context["created_id"] for k in body)
    assert all("client_secret" not in k for k in body)
    assert all("secret_hash" not in k for k in body)
