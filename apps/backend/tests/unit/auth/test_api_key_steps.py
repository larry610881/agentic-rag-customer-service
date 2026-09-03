"""租戶 API key BDD Step Definitions（Issue #67 P2）— domain + use cases，mock repo。"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.auth.api_key_use_cases import (
    AuthenticateApiClientUseCase,
    CreateApiKeyCommand,
    CreateApiKeyUseCase,
    ExchangeClientCredentialsUseCase,
    RevokeApiKeyUseCase,
)
from src.domain.auth.api_key import (
    ApiKey,
    InvalidClientError,
    InvalidScopeError,
    hash_client_secret,
    new_salt,
    secret_display_prefix,
)
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError
from src.infrastructure.auth.jwt_service import JWTService

scenarios("unit/auth/api_key.feature")


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def ctx():
    repo = AsyncMock()
    store: dict[str, ApiKey] = {}

    async def save(key):
        store[key.id] = key

    async def find_by_id(key_id):
        return store.get(key_id)

    repo.save.side_effect = save
    repo.find_by_id.side_effect = find_by_id
    audit = AsyncMock()
    return {
        "repo": repo,
        "store": store,
        "audit": audit,
        "jwt": JWTService("unit-secret"),
        "secrets": {},
    }


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse(
    '租戶 "{tenant}" 的 API key 建立命令 名稱 "{name}" scopes "{scopes}"'
))
def create_command(ctx, tenant, name, scopes):
    ctx["command"] = CreateApiKeyCommand(
        tenant_id=tenant, name=name, scopes=scopes.split(), actor_user_id="u1"
    )


@given(parsers.parse(
    '租戶 "{tenant}" 已有 API key "{key_id}" scopes "{scopes}" token_version {ver:d}'
))
def existing_key(ctx, tenant, key_id, scopes, ver):
    secret = "ark_dev_" + "x" * 32
    salt = new_salt()
    key = ApiKey(
        id=key_id,
        tenant_id=tenant,
        name="k",
        scopes=scopes.split(),
        secret_hash=hash_client_secret(secret, salt),
        secret_salt=salt,
        secret_prefix=secret_display_prefix(secret),
        token_version=ver,
    )
    ctx["store"][key_id] = key
    ctx["secrets"][key_id] = secret


@given(parsers.parse('key "{key_id}" 狀態為 "{state}"'))
def key_state(ctx, key_id, state):
    key = ctx["store"][key_id]
    now = datetime.now(timezone.utc)
    if state == "revoked":
        key.revoked_at = now
    elif state == "expired":
        key.expires_at = now - timedelta(seconds=1)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("執行建立 API key")
def do_create(ctx):
    uc = CreateApiKeyUseCase(ctx["repo"], env_label="dev", audit=ctx["audit"])
    try:
        ctx["result"] = _run(uc.execute(ctx["command"]))
    except ValidationError as e:
        ctx["error"] = e


@when(parsers.parse('以租戶 "{tenant}" 撤銷 API key "{key_id}"'))
def do_revoke(ctx, tenant, key_id):
    uc = RevokeApiKeyUseCase(ctx["repo"], audit=ctx["audit"])
    try:
        ctx["result"] = _run(
            uc.execute(key_id, tenant_id=tenant, actor_user_id="u1")
        )
    except EntityNotFoundError as e:
        ctx["error"] = e


def _exchange(ctx, client_id, secret, scope):
    uc = ExchangeClientCredentialsUseCase(ctx["repo"], ctx["jwt"])
    try:
        ctx["token"] = _run(
            uc.execute(
                client_id=client_id,
                client_secret=secret,
                scope=None if scope in ("", "-") else scope,
            )
        )
    except (InvalidClientError, InvalidScopeError) as e:
        ctx["error"] = e


@when(parsers.parse('以 key "{key_id}" 的正確 secret 換票 scope "{scope}"'))
def exchange_correct(ctx, key_id, scope):
    _exchange(ctx, key_id, ctx["secrets"][key_id], scope)


@when(parsers.parse('以 key "{client_id}" 的 "{which}" secret 換票 scope "{scope}"'))
def exchange_variant(ctx, client_id, which, scope):
    secret = ctx["secrets"].get(client_id, "ark_dev_" + "x" * 32)
    if which == "wrong":
        secret = "ark_dev_" + "y" * 32
    _exchange(ctx, client_id, secret, scope)


@when(parsers.parse('驗證 client "{client_id}" ver {ver:d} 的 api_access 票'))
def do_authenticate(ctx, client_id, ver):
    uc = AuthenticateApiClientUseCase(ctx["repo"])
    key = ctx["store"].get(client_id)
    payload = {
        "sub": client_id,
        "type": "api_access",
        "tenant_id": key.tenant_id if key else "t1",
        "scopes": key.scopes if key else [],
        "bot_ids": [],
        "ver": ver,
    }
    try:
        ctx["principal"] = _run(uc.execute(payload))
    except InvalidClientError as e:
        ctx["error"] = e


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse('回傳的 secret 以 "{prefix}" 開頭且長度為 {length:d}'))
def secret_shape(ctx, prefix, length):
    secret = ctx["result"].client_secret
    assert secret.startswith(prefix)
    assert len(secret) == length


@then("儲存的 key 不含明文 secret 且 secret_prefix 為 secret 前 12 碼")
def stored_hash_only(ctx):
    key = ctx["result"].key
    secret = ctx["result"].client_secret
    assert secret not in (key.secret_hash, key.secret_salt, key.secret_prefix)
    assert key.secret_prefix == secret[:12]
    ctx["repo"].save.assert_awaited_once()


@then("儲存的 key 能驗證該 secret")
def stored_verifies(ctx):
    assert ctx["result"].key.verify_secret(ctx["result"].client_secret)
    assert not ctx["result"].key.verify_secret("ark_dev_" + "z" * 32)


@then(parsers.parse('稽核紀錄應記錄 "{entity}" 的 "{action}"'))
def audit_recorded(ctx, entity, action):
    calls = [c.kwargs for c in ctx["audit"].record.await_args_list]
    assert any(
        c["entity_type"] == entity and c["action"] == action for c in calls
    ), calls


@then("建立應失敗並提示未知 scope")
def create_failed_unknown_scope(ctx):
    assert isinstance(ctx.get("error"), ValidationError)
    assert "Unknown scopes" in ctx["error"].message
    ctx["repo"].save.assert_not_awaited()


@then(parsers.parse('key "{key_id}" 應為已撤銷且 token_version 為 {ver:d}'))
def key_revoked(ctx, key_id, ver):
    key = ctx["store"][key_id]
    assert key.revoked_at is not None
    assert not key.is_active()
    assert key.token_version == ver


@then("撤銷應失敗為找不到")
def revoke_not_found(ctx):
    assert isinstance(ctx.get("error"), EntityNotFoundError)
    assert ctx["store"]["k1"].revoked_at is None


@then(parsers.parse(
    '換票成功且票的 type 為 "{ttype}" tenant_id "{tenant}" '
    'scopes "{scopes}" ver {ver:d}'
))
def exchange_ok(ctx, ttype, tenant, scopes, ver):
    payload = ctx["jwt"].decode_token(ctx["token"].access_token)
    assert payload["type"] == ttype
    assert payload["tenant_id"] == tenant
    assert payload["scopes"] == scopes.split()
    assert payload["ver"] == ver
    assert payload["iss"] == "agentic-rag" and payload["aud"] == "agentic-rag-api"
    assert payload["jti"]
    assert ctx["token"].expires_in == 900


@then(parsers.parse('key "{key_id}" 的 last_used_at 應被更新'))
def last_used_touched(ctx, key_id):
    ctx["repo"].touch_last_used.assert_awaited_once()
    assert ctx["repo"].touch_last_used.await_args.args[0] == key_id


@then(parsers.parse('換票成功且回應 scope 為 "{scope}"'))
def exchange_scope(ctx, scope):
    assert ctx["token"].scope == scope


@then("換票應失敗為 invalid_scope")
def exchange_invalid_scope(ctx):
    assert isinstance(ctx.get("error"), InvalidScopeError)


@then("換票應失敗為 invalid_client")
def exchange_invalid_client(ctx):
    assert isinstance(ctx.get("error"), InvalidClientError)
    assert ctx["error"].message == "invalid_client"


@then("驗票應失敗為 invalid_client")
def auth_invalid(ctx):
    assert isinstance(ctx.get("error"), InvalidClientError)


@then(parsers.parse('驗票成功且 principal 的 tenant_id 為 "{tenant}"'))
def auth_ok(ctx, tenant):
    assert ctx["principal"].tenant_id == tenant
    assert ctx["principal"].client_id == "k1"
