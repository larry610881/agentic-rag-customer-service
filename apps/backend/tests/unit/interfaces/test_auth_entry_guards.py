"""認證 / 版本 / 限流入口（deps.py、client_version_middleware、rate_limit_middleware）。

Issue #101 B8 覆蓋率下限。守：
- bearer 過期 → 401 token_expired；錯簽章 → 401 token_invalid
- refresh 票不得當 access 用；缺 sub 的 user / legacy 票被拒；token_version 撤銷
- api client：撤銷 → 401 token_revoked；未宣告 scope 的端點 → 403；bot 範圍
- 角色閘門：非指定角色 403
- 426：舊版客戶端；非 http scope 直通
- 429：超限回 429 + Retry-After；告警失敗不影響 429；豁免路徑不計數；
  abuse L2+ 主體加一層降速、儲存失效放行、monitor 模式不降速
"""

import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.domain.auth.api_key import ApiPrincipal, InvalidClientError
from src.domain.ratelimit.rate_limiter_service import RateLimitResult
from src.infrastructure.auth.in_memory_token_stores import (
    InMemoryTokenRevocationStore,
)
from src.infrastructure.auth.jwt_service import JWTService
from src.infrastructure.ratelimit.config_loader import ResolvedRateLimitConfig
from src.interfaces.api.client_version_middleware import ClientVersionMiddleware
from src.interfaces.api.deps import (
    CurrentTenant,
    authenticate,
    ensure_bot_allowed,
    get_current_tenant,
    require_role,
    require_scope,
)
from src.interfaces.api.rate_limit_middleware import (
    RateLimitMiddleware,
    _resolve_endpoint_group,
)

_SECRET = "unit-test-secret-key-0123456789abcdef"


def _run(coro):
    return asyncio.run(coro)


def _svc(**kw) -> JWTService:
    return JWTService(_SECRET, **kw)


def _auth(token: str, *, svc=None, api_auth=None, revocation=None):
    return _run(
        authenticate(
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=token
            ),
            jwt_service=svc or _svc(),
            api_client_auth=api_auth or AsyncMock(),
            revocation_store=revocation or InMemoryTokenRevocationStore(),
        )
    )


def _code(exc: HTTPException) -> str:
    return getattr(exc, "code", "")


def _auth_error(token: str, **kw) -> HTTPException:
    with pytest.raises(HTTPException) as ei:
        _auth(token, **kw)
    return ei.value


# ============================================================== deps.authenticate


def test_expired_bearer_is_401_token_expired():
    tok = _svc(access_token_expire_minutes=-1).create_user_token("u", "t", "user")
    err = _auth_error(tok)
    assert err.status_code == 401 and _code(err) == "token_expired"


def test_wrong_signature_is_401_token_invalid():
    tok = JWTService("other-secret-key-yyyyyyyyyyyyyyyyyyy").create_user_token(
        "u", "t", "system_admin"
    )
    err = _auth_error(tok)
    assert err.status_code == 401 and _code(err) == "token_invalid"


def test_garbage_bearer_is_401():
    assert _auth_error("not-a-jwt").status_code == 401


@pytest.mark.parametrize("kind", ["user", "tenant"])
def test_refresh_token_cannot_access_resources(kind):
    svc = _svc()
    tok = (
        svc.create_refresh_token("u", "t", "user")
        if kind == "user"
        else svc.create_tenant_refresh_token("t")
    )
    err = _auth_error(tok, svc=svc)
    assert err.status_code == 401 and _code(err) == "token_type_not_allowed"


def test_user_token_ok_and_revoked_by_token_version():
    svc = _svc()
    rev = InMemoryTokenRevocationStore()
    old = svc.create_user_token("u1", "t1", "tenant_admin", version=1)
    cur = _auth(old, svc=svc, revocation=rev)
    assert (cur.tenant_id, cur.user_id, cur.role) == ("t1", "u1", "tenant_admin")

    _run(rev.revoke_user_before("u1", 2, 900))  # 改密碼
    err = _auth_error(old, svc=svc, revocation=rev)
    assert err.status_code == 401 and _code(err) == "token_revoked"
    # 新版號票仍可用
    new = svc.create_user_token("u1", "t1", "tenant_admin", version=2)
    assert _auth(new, svc=svc, revocation=rev).user_id == "u1"


def test_user_token_without_sub_rejected():
    svc = _svc()
    payload = svc._base_claims(
        token_type="user_access", sub="", ttl=timedelta(minutes=1)
    )
    err = _auth_error(svc._encode(payload), svc=svc)
    assert err.status_code == 401


def test_legacy_tenant_token_and_missing_sub():
    svc = _svc()
    assert _auth(svc.create_tenant_token("t9"), svc=svc) == CurrentTenant("t9")
    payload = svc._base_claims(
        token_type="tenant_access", sub="", ttl=timedelta(minutes=1)
    )
    assert _auth_error(svc._encode(payload), svc=svc).status_code == 401


def test_api_client_token_resolved_and_revoked():
    svc = _svc()
    tok, _ = svc.create_api_access_token(
        client_id="c1", tenant_id="t1", scopes=["chat"], bot_ids=["b1"], version=1
    )
    api_auth = AsyncMock()
    api_auth.execute.return_value = ApiPrincipal("c1", "t1", ("chat",), ("b1",))
    cur = _auth(tok, svc=svc, api_auth=api_auth)
    assert cur.is_api_client and cur.client_id == "c1" and cur.tenant_id == "t1"

    api_auth.execute.side_effect = InvalidClientError()
    err = _auth_error(tok, svc=svc, api_auth=api_auth)
    assert err.status_code == 401 and _code(err) == "token_revoked"


# ============================================================== role / scope


_API = CurrentTenant("t1", role="api_client", client_id="c1", scopes=("chat",),
                     bot_ids=("b1",))
_ADMIN = CurrentTenant("t1", user_id="u1", role="tenant_admin")


def _status(coro) -> int:
    with pytest.raises(HTTPException) as ei:
        _run(coro)
    return ei.value.status_code


def test_api_client_blocked_from_human_endpoints():
    assert _status(get_current_tenant(tenant=_API)) == 403
    assert _run(get_current_tenant(tenant=_ADMIN)) is _ADMIN


def test_require_role():
    check = require_role("system_admin", "tenant_admin")
    assert _run(check(tenant=_ADMIN)) is _ADMIN
    assert _status(check(tenant=CurrentTenant("t1", role="user"))) == 403


def test_require_scope():
    assert _run(require_scope("chat")(tenant=_API)) is _API
    assert _status(require_scope("admin")(tenant=_API)) == 403
    # 人類使用者不受 scope 限制
    assert _run(require_scope("admin")(tenant=_ADMIN)) is _ADMIN


def test_bot_scope():
    ensure_bot_allowed(_API, "b1")
    ensure_bot_allowed(_ADMIN, "any")
    ensure_bot_allowed(CurrentTenant("t1", role="api_client"), "any")  # 未綁 bot
    for bot in ("b2", None):
        with pytest.raises(HTTPException) as ei:
            ensure_bot_allowed(_API, bot)
        assert ei.value.status_code == 403


# ============================================================== ASGI helpers


def _call(mw, scope):
    sent: list = []

    async def receive():
        return {"type": "http.request"}

    async def send(msg):
        sent.append(msg)

    _run(mw(scope, receive, send))
    return sent


def _ok_app():
    calls: list = []

    async def app(scope, receive, send):
        calls.append(scope["type"])
        if scope["type"] == "http":
            await send({"type": "http.response.start", "status": 200,
                        "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

    return app, calls


def _http(path="/api/v1/x", headers=None, client=("10.0.0.1", 1)):
    return {
        "type": "http",
        "path": path,
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        "client": client,
    }


# ============================================================== client version


def test_client_version_426_for_old_client_and_pass_for_new():
    app, calls = _ok_app()
    mw = ClientVersionMiddleware(app, min_version="2.1.0")
    sent = _call(mw, _http(headers={"X-Client-Version": "2.0.9"}))
    assert sent[0]["status"] == 426
    assert json.loads(sent[1]["body"])["code"] == "client_upgrade_required"
    assert calls == []
    assert _call(mw, _http(headers={"X-Client-Version": "2.1.0"}))[0]["status"] == 200


def test_client_version_non_http_passthrough():
    app, calls = _ok_app()
    _call(ClientVersionMiddleware(app, min_version="9.0.0"), {"type": "lifespan"})
    assert calls == ["lifespan"]


# ============================================================== rate limit


def _limiter(allowed=True, remaining=5):
    lim = AsyncMock()
    lim.check_rate_limit.return_value = RateLimitResult(
        allowed=allowed, remaining=remaining, retry_after=None if allowed else 7
    )
    return lim


def _loader():
    loader = AsyncMock()
    loader.get_config.return_value = ResolvedRateLimitConfig(100, 120, 50)
    return loader


def _rl(app, limiter, **kw):
    return RateLimitMiddleware(app, limiter, _loader(), _SECRET, **kw)


def _bearer(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_resolve_endpoint_group():
    assert _resolve_endpoint_group("/api/v1/widget/abc/config") == "widget_issue"
    assert _resolve_endpoint_group("/api/v1/auth/login") == "auth"
    assert _resolve_endpoint_group("/api/v1/auth/me") is None
    assert _resolve_endpoint_group("/api/v1/bots") == "general"
    assert _resolve_endpoint_group("/assets/app.js") is None


def test_rate_limit_exempt_and_non_http_paths_skip_limiter():
    app, calls = _ok_app()
    lim = _limiter()
    mw = _rl(app, lim)
    _call(mw, _http("/health"))
    _call(mw, {"type": "websocket", "path": "/api/v1/x"})
    assert calls == ["http", "websocket"]
    lim.check_rate_limit.assert_not_awaited()


def test_rate_limit_429_even_if_alert_hook_fails():
    app, calls = _ok_app()
    alerts = AsyncMock()
    alerts.rate_limited.side_effect = RuntimeError("teams down")
    tok = _svc().create_user_token("u1", "t1", "user")
    sent = _call(
        _rl(app, _limiter(allowed=False), abuse_alerts=alerts),
        _http(headers=_bearer(tok)),
    )
    assert sent[0]["status"] == 429
    assert (b"retry-after", b"7") in sent[0]["headers"]
    assert json.loads(sent[1]["body"])["code"] == "rate_limited"
    alerts.rate_limited.assert_awaited_once_with("t1")
    assert calls == []


def test_rate_limit_remaining_header_and_ip_fallback_on_bad_jwt():
    app, _ = _ok_app()
    lim = _limiter(remaining=3)
    sent = _call(
        _rl(app, lim),
        _http(headers={"Authorization": "Bearer garbage",
                       "X-Visitor-Id": "v1"}),
    )
    assert (b"x-ratelimit-remaining", b"3") in sent[0]["headers"]
    keys = [c.args[0] for c in lim.check_rate_limit.await_args_list]
    # 無效 JWT → 無 tenant，退回 socket IP 維度
    assert "rl:ip:10.0.0.1:general:60" in keys


def test_rate_limit_ip_unknown_without_client():
    app, _ = _ok_app()
    lim = _limiter()
    _call(_rl(app, lim), _http(client=None))
    keys = [c.args[0] for c in lim.check_rate_limit.await_args_list]
    assert "rl:ip:unknown:general:60" in keys


class _Store:
    def __init__(self, levels=None, fail=False):
        self.levels = levels or {}
        self.fail = fail

    async def get_level(self, key):
        if self.fail:
            raise ConnectionError("down")
        return self.levels.get(key)


def _abuse_keys(store, token, headers=None, policy=None):
    app, _ = _ok_app()
    lim = _limiter()
    _call(
        _rl(app, lim, abuse_store=store, abuse_slow_rpm=5,
            abuse_policy_provider=policy),
        _http(headers={**_bearer(token), **(headers or {})}),
    )
    return {c.args[0]: c.args[1] for c in lim.check_rate_limit.await_args_list}


def test_abuse_level2_api_client_end_user_is_slowed():
    tok, _ = _svc().create_api_access_token(
        client_id="c1", tenant_id="t1", scopes=[], bot_ids=[], version=1
    )
    store = _Store({"abuse:t1:end_user:eu9": (2, 60)})
    keys = _abuse_keys(store, tok, headers={"X-End-User-Id": "eu9"})
    assert keys["rl:abuse:abuse:t1:end_user:eu9:60"] == 5


def test_abuse_level2_api_client_without_end_user_uses_client_subject():
    tok, _ = _svc().create_api_access_token(
        client_id="c1", tenant_id="t1", scopes=[], bot_ids=[], version=1
    )
    store = _Store({"abuse:t1:client:c1": (3, 60)})
    assert "rl:abuse:abuse:t1:client:c1:60" in _abuse_keys(store, tok)


def test_abuse_widget_visitor_level1_not_slowed():
    tok, _ = _svc().create_widget_token(
        bot_id="b", tenant_id="t1", origin="o", visitor_id="v1"
    )
    store = _Store({"abuse:t1:visitor:v1": (1, 60)})
    assert not any(k.startswith("rl:abuse") for k in _abuse_keys(store, tok))


def test_abuse_store_failure_fails_open():
    tok = _svc().create_user_token("u1", "t1", "user")
    keys = _abuse_keys(_Store(fail=True), tok)
    assert not any(k.startswith("rl:abuse") for k in keys)
    assert keys["rl:t1:general:60"] == 100  # 租戶層未被減半


def test_tenant_aggregate_lock_halves_tenant_limit():
    tok = _svc().create_user_token("u1", "t1", "user")
    keys = _abuse_keys(_Store({"abuse:t1:tenant:t1": (1, 60)}), tok)
    assert keys["rl:t1:general:60"] == 50


@pytest.mark.parametrize(
    ("policy", "slowed"),
    [
        (SimpleNamespace(enabled=True, mode=SimpleNamespace(value="monitor")), False),
        (SimpleNamespace(enabled=False, mode="enforce"), False),
        (SimpleNamespace(enabled=True, mode="enforce"), True),
        (None, True),  # 取不到設定 → fail-safe 視為 enforce
    ],
)
def test_abuse_slowdown_respects_tenant_mode(policy, slowed):
    tok = _svc().create_user_token("u1", "t1", "user")
    provider = AsyncMock()
    if policy is None:
        provider.policy_for.side_effect = RuntimeError("db down")
    else:
        provider.policy_for.return_value = policy
    store = _Store({"abuse:t1:user:u1": (2, 60)})
    keys = _abuse_keys(store, tok, policy=provider)
    assert ("rl:abuse:abuse:t1:user:u1:60" in keys) is slowed
