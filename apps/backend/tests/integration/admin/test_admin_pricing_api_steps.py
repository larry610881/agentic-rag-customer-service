"""Admin Pricing API — BDD integration step defs (S-Pricing.1)"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import text

scenarios("integration/admin/admin_pricing_api.feature")


@pytest.fixture
def ctx():
    return {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Given ──────────────────────────────────────────────────────


@given("系統管理員已登入")
def admin_login(ctx, admin_headers):
    ctx["headers"] = admin_headers


@given("一般租戶已登入")
def tenant_login(ctx, auth_headers):
    # auth_headers 已經是 tenant_admin，不是 system_admin → 應被擋
    ctx["headers"] = {
        k: v for k, v in auth_headers.items() if not k.startswith("_")
    }


@given(parsers.parse('系統已 seed pricing "{provider}" "{model_id}" 生效中'))
def seed_pricing_active(ctx, client, admin_headers, provider, model_id):
    resp = client.post(
        "/api/v1/admin/pricing",
        json={
            "provider": provider,
            "model_id": model_id,
            "display_name": model_id,
            "category": "llm",
            "input_price": 1.0,
            "output_price": 5.0,
            "cache_read_price": 0,
            "cache_creation_price": 0,
            "effective_from": (_now() + timedelta(seconds=1)).isoformat(),
            "note": "seed active",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    ctx["pid"] = resp.json()["id"]


@given(
    parsers.parse(
        '系統已 seed pricing "{provider}" "{model_id}" 生效中 id 為 "{pid_ignored}"'
    )
)
def seed_pricing_with_id(ctx, test_engine, provider, model_id, pid_ignored):
    # 用 raw SQL 塞 effective_from=1 小時前，避免 deactivate 時 effective_to<effective_from
    import asyncio

    pid = str(uuid4())

    async def _seed():
        async with test_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO model_pricing "
                    "(id, provider, model_id, display_name, category, "
                    "input_price, output_price, cache_read_price, cache_creation_price, "
                    "effective_from, created_by, created_at, note) "
                    "VALUES (:id, :prov, :mid, :mid, 'llm', 1.0, 5.0, 0, 0, "
                    ":ef, 'seed', :at, 'seed')"
                ),
                {
                    "id": pid,
                    "prov": provider,
                    "mid": model_id,
                    "ef": _now() - timedelta(hours=1),
                    "at": _now(),
                },
            )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_seed())
    finally:
        loop.close()
    ctx["pid"] = pid


@given(
    parsers.parse(
        'token_usage_records 在過去 1 小時有 {n:d} 筆 "{prefix}:{model_id}" usage'
    )
)
def seed_usage_rows(ctx, test_engine, n, prefix, model_id):
    import asyncio

    async def _seed():
        async with test_engine.begin() as conn:
            for i in range(n):
                await conn.execute(
                    text(
                        "INSERT INTO token_usage_records "
                        "(id, tenant_id, request_type, model, input_tokens, output_tokens, "
                        "estimated_cost, cache_read_tokens, cache_creation_tokens, created_at) "
                        "VALUES (:id, :tid, :rt, :model, :it, :ot, :cost, 0, 0, :at)"
                    ),
                    {
                        "id": str(uuid4()),
                        "tid": "test-tenant-recalc",
                        "rt": "chat_web",
                        "model": f"{prefix}:{model_id}",
                        "it": 1000,
                        "ot": 500,
                        "cost": 0.0035,
                        "at": _now() - timedelta(minutes=30),
                    },
                )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_seed())
    finally:
        loop.close()
    ctx["seeded_usage"] = n


@given(
    parsers.parse(
        '系統已 seed 新版本 pricing "{provider}" "{model_id}" input={inp:g} output={out:g}'
    )
)
def seed_new_pricing_version(ctx, client, admin_headers, provider, model_id, inp, out):
    resp = client.post(
        "/api/v1/admin/pricing",
        json={
            "provider": provider,
            "model_id": model_id,
            "display_name": model_id,
            "category": "llm",
            "input_price": inp,
            "output_price": out,
            "cache_read_price": 0,
            "cache_creation_price": 0,
            "effective_from": (_now() + timedelta(seconds=1)).isoformat(),
            "note": "seed new version",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    ctx["pid"] = resp.json()["id"]


@given("系統已執行過 1 次 recalculate audit")
def seed_audit(ctx, test_engine):
    import asyncio

    async def _seed():
        pid = str(uuid4())
        async with test_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO model_pricing "
                    "(id, provider, model_id, display_name, category, "
                    "input_price, output_price, cache_read_price, cache_creation_price, "
                    "effective_from, created_by, created_at, note) "
                    "VALUES (:id, 'openai', 'gpt-5', 'GPT-5', 'llm', "
                    "1.25, 10.0, 0, 0, :ef, 'seed', :at, 'seed')"
                ),
                {"id": pid, "ef": _now() - timedelta(hours=2), "at": _now()},
            )
            await conn.execute(
                text(
                    "INSERT INTO pricing_recalc_audit "
                    "(id, pricing_id, recalc_from, recalc_to, affected_rows, "
                    "cost_before_total, cost_after_total, executed_by, executed_at, reason) "
                    "VALUES (:id, :pid, :rf, :rt, 1, 0.01, 0.012, 'admin', :eat, '測試 seed')"
                ),
                {
                    "id": str(uuid4()),
                    "pid": pid,
                    "rf": _now() - timedelta(hours=1),
                    "rt": _now(),
                    "eat": _now(),
                },
            )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_seed())
    finally:
        loop.close()


# ── When ──────────────────────────────────────────────────────


@when(parsers.parse("我送出 POST /api/v1/admin/pricing body={body}"))
def post_create(ctx, client, body):
    # "FUTURE" sentinel 轉成實際未來時間
    import json

    data = json.loads(body)
    if data.get("effective_from") == "FUTURE":
        data["effective_from"] = (_now() + timedelta(minutes=5)).isoformat()
    ctx["resp"] = client.post(
        "/api/v1/admin/pricing", json=data, headers=ctx["headers"]
    )


@when(parsers.parse("我送出 GET /api/v1/admin/pricing?provider={provider}"))
def get_list_with_provider(ctx, client, provider):
    ctx["resp"] = client.get(
        f"/api/v1/admin/pricing?provider={provider}", headers=ctx["headers"]
    )


@when("我送出 GET /api/v1/admin/pricing")
def get_list(ctx, client):
    ctx["resp"] = client.get(
        "/api/v1/admin/pricing", headers=ctx["headers"]
    )


@when(parsers.parse("我送出 POST /api/v1/admin/pricing/{pid_ignored}/deactivate"))
def post_deactivate(ctx, client, pid_ignored):
    # 忽略 feature 指定的 pid，使用實際 seed 時拿到的 uuid
    real_pid = ctx.get("pid") or pid_ignored
    ctx["resp"] = client.post(
        f"/api/v1/admin/pricing/{real_pid}/deactivate", headers=ctx["headers"]
    )


@when("我送出 POST /api/v1/admin/pricing/recalculate:dry-run body 含 pricing_id 與過去 1 小時區間")
def post_dry_run(ctx, client):
    body = {
        "pricing_id": ctx["pid"],
        "recalc_from": (_now() - timedelta(hours=1)).isoformat(),
        "recalc_to": _now().isoformat(),
    }
    ctx["resp"] = client.post(
        "/api/v1/admin/pricing/recalculate:dry-run",
        json=body,
        headers=ctx["headers"],
    )


@when(parsers.parse('我送出 POST /api/v1/admin/pricing/recalculate:execute body 含該 dry_run_token 與 reason="{reason}"'))
def post_execute(ctx, client, reason):
    token = ctx["resp"].json()["dry_run_token"]
    ctx["resp"] = client.post(
        "/api/v1/admin/pricing/recalculate:execute",
        json={"dry_run_token": token, "reason": reason},
        headers=ctx["headers"],
    )


@when("我送出 GET /api/v1/admin/pricing/recalculate-history")
def post_history(ctx, client):
    ctx["resp"] = client.get(
        "/api/v1/admin/pricing/recalculate-history",
        headers=ctx["headers"],
    )


# ── Then ──────────────────────────────────────────────────────


@then(parsers.parse("回應狀態碼為 {code:d}"))
def assert_status(ctx, code):
    actual = ctx["resp"].status_code
    assert actual == code, f"got {actual}: {ctx['resp'].text}"


@then(parsers.parse('回應中 provider 為 "{v}"'))
def assert_provider(ctx, v):
    assert ctx["resp"].json()["provider"] == v


@then(parsers.parse('回應中 model_id 為 "{v}"'))
def assert_model_id(ctx, v):
    assert ctx["resp"].json()["model_id"] == v


@then("回應中 effective_to 為 null")
def assert_effective_to_null(ctx):
    assert ctx["resp"].json()["effective_to"] is None


@then("回應中 effective_to 不為 null")
def assert_effective_to_not_null(ctx):
    assert ctx["resp"].json()["effective_to"] is not None


@then(parsers.parse('回應 items 至少含一筆 provider 為 "{v}"'))
def assert_items_provider(ctx, v):
    items = ctx["resp"].json()
    assert any(i.get("provider") == v for i in items)


@then(parsers.parse("回應 affected_rows 為 {n:d}"))
def assert_affected(ctx, n):
    assert ctx["resp"].json()["affected_rows"] == n


@then("回應含有 dry_run_token")
def assert_has_token(ctx):
    assert ctx["resp"].json().get("dry_run_token")


@then("回應 items 至少含一筆 reason 不為空")
def assert_items_have_reason(ctx):
    items = ctx["resp"].json()
    assert any((i.get("reason") or "").strip() for i in items)


# ── helpers ──────────────────────────────────────────────────────


def _seed_pricing(
    app,
    *,
    pid: str,
    provider: str,
    model_id: str,
    effective_from: datetime,
    input_price: float = 1.0,
    output_price: float = 5.0,
) -> None:
    import asyncio

    async def _run():
        session_factory = app.container.trace_session_factory()
        async with session_factory() as s:
            await s.execute(
                text(
                    "INSERT INTO model_pricing "
                    "(id, provider, model_id, display_name, category, "
                    "input_price, output_price, cache_read_price, cache_creation_price, "
                    "effective_from, created_by, note) "
                    "VALUES (:id, :prov, :mid, :dn, 'llm', :ip, :op, 0, 0, :ef, 'seed', 'seed')"
                ),
                {
                    "id": pid,
                    "prov": provider,
                    "mid": model_id,
                    "dn": model_id,
                    "ip": Decimal(str(input_price)),
                    "op": Decimal(str(output_price)),
                    "ef": effective_from,
                },
            )
            await s.commit()

    asyncio.get_event_loop().run_until_complete(_run())
