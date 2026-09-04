"""聚合層 BDD Step Definitions（Issue #68 P7d）"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from src.application.abuse.abuse_alerts import AbuseAlertService
from src.application.abuse.abuse_control_service import AbuseControlService
from src.domain.abuse.events import AbuseAlertEvent, AbuseAlertKind
from src.domain.abuse.policy import AbusePolicy, AbuseSubject, SubjectKind
from src.infrastructure.abuse.in_memory_abuse_score_store import (
    InMemoryAbuseScoreStore,
)
from src.interfaces.api.rate_limit_middleware import RateLimitMiddleware

scenarios("unit/abuse/abuse_aggregation.feature")

_T = "t1"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def ctx():
    return {"events": []}


@given("聚合層測試用的控管服務與記憶體儲存")
def service(ctx):
    ctx["now"] = 1_000_000.0
    ctx["store"] = InMemoryAbuseScoreStore(clock=lambda: ctx["now"])
    ctx["policy"] = AbusePolicy()
    ctx["audit"] = AsyncMock()

    async def publish(event: AbuseAlertEvent) -> None:
        ctx["events"].append(event)

    ctx["svc"] = AbuseControlService(
        ctx["store"], ctx["policy"], audit=ctx["audit"],
        alerts=AbuseAlertService(InMemoryAbuseScoreStore(), publish),
    )


@given(parsers.parse('政策 IP 白名單含 "{ip}"'))
def allowlist(ctx, ip):
    ctx["policy"].ip_allowlist = [ip]


@given("政策關閉 IP 層")
def ip_layer_off(ctx):
    ctx["policy"].ip_layer_enabled = False


def _hits(ctx, vid: str, ip: str, n: int = 3) -> None:
    for _ in range(n):
        _run(ctx["svc"].record(
            _T, AbuseSubject(SubjectKind.VISITOR, vid), guard_hit=True,
            channel="widget", client_ip=ip,
        ))
        ctx["now"] += 5


@when(parsers.parse('來自 IP "{ip}" 的訪客 "{vid}" 連續 {n:d} 回合 Guard 命中'))
def hits_from_ip(ctx, ip, vid, n):
    _hits(ctx, vid, ip, n)


@when(parsers.parse('來自不同 IP 的訪客 "{a}" "{b}" "{c}" 各連續 4 回合 Guard 命中'))
def hits_from_different_ips(ctx, a, b, c):
    for i, vid in enumerate((a, b, c)):
        _hits(ctx, vid, f"198.51.100.{i + 10}", 4)


def _evaluate(ctx, kind: SubjectKind, sid: str, ip: str | None = None):
    return _run(ctx["svc"].evaluate(_T, AbuseSubject(kind, sid), client_ip=ip))


@then(parsers.parse('訪客 "{vid}" 的等級為 {level:d}'))
def visitor_level(ctx, vid, level):
    assert int(_evaluate(ctx, SubjectKind.VISITOR, vid).level) == level


@then(parsers.parse('IP "{ip}" 的等級為 {level:d}'))
def ip_level(ctx, ip, level):
    locked = _run(ctx["store"].get_level(AbuseSubject(SubjectKind.IP, ip).key(_T)))
    assert (locked[0] if locked else 0) == level, locked


@then(parsers.parse("租戶聚合層的等級為 {level:d}"))
def tenant_level(ctx, level):
    locked = _run(ctx["store"].get_level(AbuseSubject(SubjectKind.TENANT, _T).key(_T)))
    assert (locked[0] if locked else 0) == level, locked


@then(parsers.parse('來自 IP "{ip}" 的新訪客 "{vid}" 評估結果為{outcome}'))
def new_visitor_outcome(ctx, ip, vid, outcome):
    d = _evaluate(ctx, SubjectKind.VISITOR, vid, ip)
    if outcome == "放行":
        assert d.effective_level == 0, d
    elif outcome == "拒絕":
        assert d.blocked and d.retry_after > 0, d
    elif outcome == "保守模式":
        assert d.conservative, d
    else:
        raise AssertionError(outcome)


@then(parsers.parse('稽核應記錄聚合層 "{kind}" 升到等級 {level:d} 且訊號含 "{signal}"'))
def audit_aggregate(ctx, kind, level, signal):
    calls = [c.kwargs for c in ctx["audit"].record.await_args_list]
    assert any(
        f":{kind}:" in c["entity_id"] and c["after"]["level"] == level
        and signal in c["after"]["signals"]
        for c in calls
    ), calls


@then(parsers.parse('應發出主體種類 "{kind}" 等級 {level:d} 的告警'))
def alert_for_kind(ctx, kind, level):
    assert any(
        e.kind is AbuseAlertKind.ESCALATION
        and e.subject_kind == kind and e.level == level
        for e in ctx["events"]
    ), ctx["events"]


# ---------------------------------------------------------------------------
# middleware
# ---------------------------------------------------------------------------


@given(parsers.parse("掛了聚合層儲存的限流中介層，租戶上限 {rpm:d}"))
def middleware(ctx, rpm):
    from src.domain.ratelimit.rate_limiter_service import RateLimitResult
    from src.infrastructure.auth.jwt_service import JWTService
    from src.infrastructure.ratelimit.config_loader import ResolvedRateLimitConfig

    limiter = AsyncMock()
    limiter.check_rate_limit = AsyncMock(
        return_value=RateLimitResult(allowed=True, remaining=99, retry_after=0)
    )
    loader = AsyncMock()
    loader.get_config = AsyncMock(return_value=ResolvedRateLimitConfig(
        requests_per_minute=rpm, burst_size=rpm, per_user_requests_per_minute=None,
    ))

    async def ok(_request):
        return JSONResponse({"ok": True})

    store = ctx.setdefault("store", InMemoryAbuseScoreStore())
    app = Starlette(routes=[Route("/api/v1/agent/chat", ok, methods=["POST"])])
    app.add_middleware(
        RateLimitMiddleware, rate_limiter=limiter, config_loader=loader,
        jwt_secret_key="test-secret", jwt_algorithm="HS256", global_rpm=1000,
        abuse_store=store,
    )
    ctx.update(
        mw_client=TestClient(app), limiter=limiter, mw_jwt=JWTService("test-secret")
    )


@given(parsers.parse("租戶聚合層已鎖定在等級 {level:d}"))
def tenant_locked(ctx, level):
    _run(ctx["store"].set_level(
        AbuseSubject(SubjectKind.TENANT, _T).key(_T), level, 600
    ))


@when("租戶使用者請求聊天端點")
def tenant_user_request(ctx):
    token = ctx["mw_jwt"].create_user_token("u1", _T, "user")
    ctx["resp"] = ctx["mw_client"].post(
        "/api/v1/agent/chat", json={}, headers={"Authorization": f"Bearer {token}"}
    )


@then(parsers.parse("租戶層限流檢查上限為 {limit:d}"))
def tenant_limit(ctx, limit):
    assert ctx["resp"].status_code == 200
    calls = [
        (c.args[0], c.args[1]) for c in ctx["limiter"].check_rate_limit.await_args_list
    ]
    tenant_calls = [c for c in calls if c[0].startswith(f"rl:{_T}:")]
    assert tenant_calls and tenant_calls[0][1] == limit, calls
