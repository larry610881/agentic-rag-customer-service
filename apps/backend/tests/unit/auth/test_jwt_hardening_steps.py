"""JWT 改版 BDD Step Definitions（Issue #67 P3）"""

import pytest
from jose import jwt
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.auth.jwt_service import JWTService

scenarios("unit/auth/jwt_hardening.feature")

_SECRET = "hardening-secret"


@pytest.fixture
def ctx():
    return {}


@given(parsers.parse('簽發者 "{iss}" 受眾 "{aud}" kid "{kid}" 的 JWT 服務'))
def service(ctx, iss, aud, kid):
    ctx["svc"] = JWTService(_SECRET, issuer=iss, audience=aud, key_id=kid)


@given(parsers.parse("允許 legacy 為 {allow} 的 JWT 服務"))
def service_legacy(ctx, allow):
    ctx["svc"] = JWTService(_SECRET, allow_legacy_tokens=(allow == "True"))


@when(parsers.parse('簽發 "{kind}" 票'))
def issue(ctx, kind):
    svc = ctx["svc"]
    if kind == "tenant_access":
        ctx["token"] = svc.create_tenant_token("t1")
    elif kind == "user_access":
        ctx["token"] = svc.create_user_token("u1", "t1", "user", version=1)
    elif kind == "refresh":
        ctx["token"] = svc.create_refresh_token("u1", "t1", "user", version=1)
    elif kind == "tenant_refresh":
        ctx["token"] = svc.create_tenant_refresh_token("t1")
    elif kind == "api_access":
        ctx["token"], _ = svc.create_api_access_token(
            client_id="c1", tenant_id="t1", scopes=["chat:send"], bot_ids=[],
            version=1,
        )
    ctx["payload"] = svc.decode_token(ctx["token"])


@when(parsers.parse(
    '簽發 user "{user}" 租戶 "{tenant}" ver {ver:d} '
    'family "{family}" jti "{jti}" 的 refresh 票'
))
def issue_refresh(ctx, user, tenant, ver, family, jti):
    ctx["token"] = ctx["svc"].create_refresh_token(
        user, tenant, "user", version=ver, family=family, jti=jti
    )
    ctx["payload"] = ctx["svc"].decode_token(ctx["token"])


@when(parsers.parse('以相同 secret 偽造 iss "{iss}" aud "{aud}" 的票'))
def forge(ctx, iss, aud):
    ctx["token"] = jwt.encode(
        {"iss": iss, "aud": aud, "sub": "u1", "type": "user_access"},
        _SECRET, algorithm="HS256",
    )


@when("以相同 secret 簽一張無 iss / aud 的舊票")
def legacy(ctx):
    ctx["token"] = jwt.encode(
        {"sub": "t1", "type": "tenant_access"}, _SECRET, algorithm="HS256"
    )


@then(parsers.parse('票的 iss 為 "{iss}" aud 為 "{aud}" type 為 "{ttype}"'))
def claims(ctx, iss, aud, ttype):
    p = ctx["payload"]
    assert p["iss"] == iss and p["aud"] == aud and p["type"] == ttype


@then("票帶有 jti 與 iat")
def jti_iat(ctx):
    assert ctx["payload"]["jti"] and ctx["payload"]["iat"]


@then(parsers.parse('票的 header kid 為 "{kid}"'))
def header_kid(ctx, kid):
    assert jwt.get_unverified_header(ctx["token"])["kid"] == kid


@then(parsers.parse('票的 ver 為 {ver:d} family 為 "{family}" jti 為 "{jti}"'))
def ver_family(ctx, ver, family, jti):
    p = ctx["payload"]
    assert p["ver"] == ver and p["family"] == family and p["jti"] == jti


@then("解析應失敗")
def decode_fails(ctx):
    with pytest.raises(ValueError):
        ctx["svc"].decode_token(ctx["token"])


@then(parsers.parse("解析結果應為 {outcome}"))
def decode_outcome(ctx, outcome):
    if outcome == "成功":
        assert ctx["svc"].decode_token(ctx["token"])["sub"] == "t1"
    else:
        with pytest.raises(ValueError):
            ctx["svc"].decode_token(ctx["token"])
