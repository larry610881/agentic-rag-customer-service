"""認證基礎設施（infrastructure/auth/*，Issue #101 B8 覆蓋率下限）。

守：JWT 過期 / 錯簽章 / 錯 iss、aud / legacy 票在 production 被拒；bcrypt 驗證與
不符；refresh family 撤銷墓碑與過期；token_version 撤銷門檻與過期；Redis 版儲存
的 key / TTL 與故障 fail-open 語意。

RedisRefreshTokenStore.rotate 的 compare-and-swap（_ROTATE_LUA）以
fakeredis[lua] 實跑：首次旋轉成功、舊票重用偵測 → 呼叫端 revoke 後整個 family
失效、同一張票並發旋轉只有一個成功。
"""

import asyncio
import base64
import json
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest
from jose import jwt

from src.domain.auth.login_attempt_tracker import LoginLockoutPolicy
from src.domain.auth.token_stores import RotationResult
from src.infrastructure.auth import in_memory_token_stores as mem
from src.infrastructure.auth.bcrypt_password_service import BcryptPasswordService
from src.infrastructure.auth.jwt_service import JWTService, TokenExpiredError
from src.infrastructure.auth.redis_login_attempt_tracker import (
    RedisLoginAttemptTracker,
)
from src.infrastructure.auth.redis_token_stores import (
    REVOKED,
    REVOKED_TTL_SECONDS,
    RedisRefreshTokenStore,
    RedisTokenRevocationStore,
)

_SECRET = "unit-test-secret-key-0123456789abcdef"


def _run(coro):
    return asyncio.run(coro)


class _BrokenRedis:
    """任何操作都丟例外：模擬 Redis 失效。"""

    def __getattr__(self, name):
        async def _fail(*a, **k):
            raise ConnectionError("redis down")

        return _fail


# ------------------------------------------------------------------ JWT


def test_jwt_ttl_properties():
    svc = JWTService(
        _SECRET, access_token_expire_minutes=15, refresh_token_expire_days=7
    )
    assert svc.access_token_ttl_seconds == 900
    assert svc.refresh_token_ttl_seconds == 7 * 86400


def test_jwt_user_token_roundtrip_carries_claims():
    svc = JWTService(_SECRET, key_id="k9")
    tok = svc.create_user_token("u1", "t1", "tenant_admin", version=3)
    assert jwt.get_unverified_header(tok)["kid"] == "k9"
    p = svc.decode_token(tok)
    assert (p["sub"], p["tenant_id"], p["role"], p["ver"], p["type"]) == (
        "u1",
        "t1",
        "tenant_admin",
        3,
        "user_access",
    )


def test_jwt_expired_token_raises_token_expired():
    svc = JWTService(_SECRET, access_token_expire_minutes=-1)
    tok = svc.create_user_token("u1", "t1", "user")
    with pytest.raises(TokenExpiredError):
        svc.decode_token(tok)


def test_jwt_wrong_signature_rejected_not_as_expired():
    tok = JWTService("another-secret-key-xxxxxxxxxxxxxxxxx").create_user_token(
        "u1", "t1", "system_admin"
    )
    with pytest.raises(ValueError, match="Invalid token") as ei:
        JWTService(_SECRET).decode_token(tok)
    assert not isinstance(ei.value, TokenExpiredError)


def test_jwt_alg_none_rejected():
    def b64(d: dict) -> str:
        raw = json.dumps(d).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    exp = int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())
    forged = (
        b64({"alg": "none", "typ": "JWT"})
        + "."
        + b64({"sub": "u1", "type": "user_access", "role": "system_admin",
               "exp": exp})
        + "."
    )
    with pytest.raises(ValueError):
        JWTService(_SECRET).decode_token(forged)


def test_jwt_wrong_issuer_or_audience_rejected():
    other_iss = JWTService(_SECRET, issuer="evil").create_user_token("u", "t", "r")
    other_aud = JWTService(_SECRET, audience="other").create_user_token("u", "t", "r")
    svc = JWTService(_SECRET)
    with pytest.raises(ValueError, match="issuer"):
        svc.decode_token(other_iss)
    with pytest.raises(ValueError, match="audience"):
        svc.decode_token(other_aud)


def test_jwt_audience_list_accepted_when_contains_ours():
    now = datetime.now(timezone.utc)
    tok = jwt.encode(
        {
            "iss": "agentic-rag",
            "aud": ["x", "agentic-rag-api"],
            "sub": "u",
            "exp": now + timedelta(minutes=5),
        },
        _SECRET,
    )
    assert JWTService(_SECRET).decode_token(tok)["sub"] == "u"


def test_jwt_legacy_token_without_issuer_only_allowed_in_legacy_mode():
    now = datetime.now(timezone.utc)
    legacy = jwt.encode(
        {"sub": "t1", "exp": now + timedelta(minutes=5)}, _SECRET, algorithm="HS256"
    )
    assert JWTService(_SECRET, allow_legacy_tokens=True).decode_token(legacy)[
        "sub"
    ] == "t1"
    with pytest.raises(ValueError, match="missing issuer"):
        JWTService(_SECRET, allow_legacy_tokens=False).decode_token(legacy)


def test_jwt_refresh_tokens_carry_family_and_jti():
    svc = JWTService(_SECRET)
    p = svc.decode_token(
        svc.create_refresh_token("u1", None, "user", 2, family="f1", jti="j1")
    )
    assert (p["type"], p["family"], p["jti"], p["ver"]) == ("refresh", "f1", "j1", 2)
    assert "tenant_id" not in p
    p = svc.decode_token(svc.create_tenant_refresh_token("t1", family="f2", jti="j2"))
    assert (p["type"], p["sub"], p["family"], p["jti"]) == (
        "tenant_refresh",
        "t1",
        "f2",
        "j2",
    )
    assert "family" not in svc.decode_token(svc.create_tenant_refresh_token("t1"))


def test_jwt_widget_token_binds_bot_origin_visitor():
    svc = JWTService(_SECRET, widget_token_expire_seconds=120)
    tok, ttl = svc.create_widget_token(
        bot_id="b1", tenant_id="t1", origin="https://a.example", visitor_id="v1"
    )
    p = svc.decode_token(tok)
    assert ttl == 120
    assert (p["sub"], p["tenant_id"], p["origin"], p["visitor_id"]) == (
        "b1",
        "t1",
        "https://a.example",
        "v1",
    )
    assert "end_user_id" not in p


# ------------------------------------------------------------------ bcrypt


def test_bcrypt_verify_and_mismatch():
    svc = BcryptPasswordService(rounds=4)
    h = svc.hash_password("correct horse")
    assert h != "correct horse" and h.startswith("$2")
    assert svc.verify_password("correct horse", h) is True
    assert svc.verify_password("Correct horse", h) is False
    # 同密碼兩次雜湊不同（有 salt）
    assert svc.hash_password("correct horse") != h


# ------------------------------------------------------------ in-memory stores


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(mem.time, "monotonic", lambda: now[0])
    return now


def test_memory_refresh_store_rotation_reuse_revoke(clock):
    s = mem.InMemoryRefreshTokenStore()
    assert _run(s.rotate("f", "j0", "j1", 60)) == RotationResult.UNKNOWN
    _run(s.begin("f", "j0", 60))
    assert _run(s.rotate("f", "j0", "j1", 60)) == RotationResult.OK
    # 舊 jti 再用一次 = 重用
    assert _run(s.rotate("f", "j0", "j2", 60)) == RotationResult.REUSED
    _run(s.revoke("f"))
    # 撤銷墓碑：連最新 jti 都拒
    assert _run(s.rotate("f", "j1", "j2", 60)) == RotationResult.REUSED


def test_memory_refresh_store_family_expires(clock):
    s = mem.InMemoryRefreshTokenStore()
    _run(s.begin("f", "j0", 60))
    clock[0] += 61
    assert _run(s.rotate("f", "j0", "j1", 60)) == RotationResult.UNKNOWN


def test_memory_revocation_store_min_version_and_expiry(clock):
    s = mem.InMemoryTokenRevocationStore()
    assert _run(s.min_version("u1")) is None
    _run(s.revoke_user_before("u1", 4, 900))
    assert _run(s.min_version("u1")) == 4
    assert _run(s.min_version("u2")) is None  # 不影響其他使用者
    clock[0] += 901
    assert _run(s.min_version("u1")) is None


# ------------------------------------------------------------ redis stores


def test_redis_refresh_store_begin_and_revoke_keys_and_ttl():
    r = fakeredis.FakeAsyncRedis()
    s = RedisRefreshTokenStore(r)

    async def main():
        await s.begin("fam", "j0", 3600)
        assert await r.get("rt:family:fam") == b"j0"
        assert 0 < await r.ttl("rt:family:fam") <= 3600
        await s.revoke("fam")
        assert (await r.get("rt:family:fam")).decode() == REVOKED
        assert await r.ttl("rt:family:fam") > 3600
        assert await r.ttl("rt:family:fam") <= REVOKED_TTL_SECONDS

    _run(main())


class _EvalStub:
    def __init__(self, result) -> None:
        self.result = result
        self.args: tuple = ()

    async def eval(self, *args):
        self.args = args
        return self.result


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"ok", RotationResult.OK),
        (b"reused", RotationResult.REUSED),
        ("unknown", RotationResult.UNKNOWN),
    ],
)
def test_redis_refresh_rotate_maps_script_result(raw, expected):
    stub = _EvalStub(raw)
    assert _run(RedisRefreshTokenStore(stub).rotate("fam", "j0", "j1", 60)) == expected
    # KEYS[1]=family key，ARGV = presented, new, ttl（對應 Lua 腳本順序）
    assert stub.args[1:] == (1, "rt:family:fam", "j0", "j1", 60)


def test_redis_stores_fail_open_when_redis_down():
    broken = _BrokenRedis()
    rs = RedisRefreshTokenStore(broken)
    rv = RedisTokenRevocationStore(broken)

    async def main():
        await rs.begin("f", "j", 60)
        await rs.revoke("f")
        assert await rs.rotate("f", "j", "k", 60) == RotationResult.OK
        await rv.revoke_user_before("u", 2, 60)
        assert await rv.min_version("u") is None

    _run(main())


def test_redis_revocation_store_roundtrip_and_ttl():
    r = fakeredis.FakeAsyncRedis()
    s = RedisTokenRevocationStore(r)

    async def main():
        assert await s.min_version("u1") is None
        await s.revoke_user_before("u1", 5, 900)
        assert await s.min_version("u1") == 5
        assert 0 < await r.ttl("rev:user:u1") <= 900
        await r.set("rev:user:u2", "garbage")
        assert await s.min_version("u2") is None

    _run(main())


def test_redis_revocation_store_accepts_str_responses():
    r = fakeredis.FakeAsyncRedis(decode_responses=True)
    s = RedisTokenRevocationStore(r)

    async def main():
        await s.revoke_user_before("u1", 7, 60)
        assert await s.min_version("u1") == 7

    _run(main())


# ------------------------------------------------------------ login tracker


def test_login_tracker_locks_after_max_failures_and_reset_clears():
    r = fakeredis.FakeAsyncRedis()
    t = RedisLoginAttemptTracker(
        r, LoginLockoutPolicy(max_failures=3, lockout_seconds=300)
    )

    async def main():
        assert await t.record_failure("a@x") == 0
        assert 0 < await r.ttl("login:fail:a@x") <= 900
        assert await t.record_failure("a@x") == 0
        assert await t.record_failure("a@x") == 300
        assert 0 < await t.retry_after("a@x") <= 300
        assert await t.retry_after("b@x") == 0
        await t.reset("a@x")
        assert await t.retry_after("a@x") == 0
        assert await r.exists("login:fail:a@x", "login:lock:a@x") == 0

    _run(main())


def test_login_tracker_fail_open_when_redis_down():
    t = RedisLoginAttemptTracker(_BrokenRedis(), LoginLockoutPolicy())

    async def main():
        assert await t.retry_after("a") == 0
        assert await t.record_failure("a") == 0
        await t.reset("a")

    _run(main())


# ------------------------------------------------------ _ROTATE_LUA（真腳本）


def test_redis_rotate_lua_first_rotation_ok_and_ttl_renewed():
    r = fakeredis.FakeAsyncRedis()
    s = RedisRefreshTokenStore(r)

    async def main():
        await s.begin("fam", "j0", 100)
        assert await s.rotate("fam", "j0", "j1", 3600) is RotationResult.OK
        assert await r.get("rt:family:fam") == b"j1"
        assert 100 < await r.ttl("rt:family:fam") <= 3600
        # 鏈式旋轉：用最新 jti 可繼續換
        assert await s.rotate("fam", "j1", "j2", 3600) is RotationResult.OK

    _run(main())


def test_redis_rotate_lua_unknown_family():
    r = fakeredis.FakeAsyncRedis()
    s = RedisRefreshTokenStore(r)

    async def main():
        assert await s.rotate("nope", "j0", "j1", 60) is RotationResult.UNKNOWN
        assert await r.exists("rt:family:nope") == 0  # 未知 family 不得被建立

    _run(main())


def test_redis_rotate_lua_reuse_detected_then_family_revoked():
    """被竊的舊票回來換 → REUSED 且不改狀態；呼叫端（RefreshTokenUseCase）依契約
    revoke 後，連合法持有者手上的最新票也失效。"""
    r = fakeredis.FakeAsyncRedis()
    s = RedisRefreshTokenStore(r)

    async def main():
        await s.begin("fam", "j0", 3600)
        assert await s.rotate("fam", "j0", "j1", 3600) is RotationResult.OK
        assert await s.rotate("fam", "j0", "jX", 3600) is RotationResult.REUSED
        assert await r.get("rt:family:fam") == b"j1"  # CAS 失敗不得覆寫
        await s.revoke("fam")
        for presented in ("j1", "j0", REVOKED):
            got = await s.rotate("fam", presented, "jY", 3600)
            assert got is RotationResult.REUSED
        assert (await r.get("rt:family:fam")).decode() == REVOKED

    _run(main())


def test_redis_rotate_lua_other_family_unaffected():
    r = fakeredis.FakeAsyncRedis()
    s = RedisRefreshTokenStore(r)

    async def main():
        await s.begin("fam-a", "a0", 3600)
        await s.begin("fam-b", "b0", 3600)
        await s.revoke("fam-a")
        assert await s.rotate("fam-b", "b0", "b1", 3600) is RotationResult.OK

    _run(main())


def test_redis_rotate_lua_concurrent_double_rotate_only_one_wins():
    r = fakeredis.FakeAsyncRedis()
    s = RedisRefreshTokenStore(r)

    async def main():
        await s.begin("fam", "j0", 3600)
        results = await asyncio.gather(
            *(s.rotate("fam", "j0", f"new-{i}", 3600) for i in range(5))
        )
        assert results.count(RotationResult.OK) == 1
        assert results.count(RotationResult.REUSED) == 4
        winner = results.index(RotationResult.OK)
        assert (await r.get("rt:family:fam")).decode() == f"new-{winner}"

    _run(main())
