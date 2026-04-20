"""Quota Email Dispatch — BDD Step Definitions (S-Token-Gov.3.5)

驗證 QuotaEmailDispatchUseCase 在 3 種情境的行為：
- 正常寄送 + mark delivered
- 無 admin email → mark delivered（避免無限重試）
- SendGrid 寄送失敗 → 不 mark（下次 cron 重試）

用 mock QuotaAlertEmailSender 取代 SendGrid（不真寄）。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from dependency_injector import providers
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.billing.email_sender import QuotaAlertEmailSender
from src.domain.billing.quota_alert import (
    ALERT_TYPE_BASE_WARNING_80,
    QuotaAlertLog,
)
from src.domain.ledger.entity import current_year_month

scenarios("integration/admin/quota_email.feature")


SEED_PLANS = [
    {
        "name": "starter",
        "base_monthly_tokens": 10_000_000,
        "addon_pack_tokens": 5_000_000,
        "base_price": 3000,
        "addon_price": 1500,
        "currency": "TWD",
        "description": "starter",
    },
]


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Mock Sender — 紀錄 call、可設定失敗
# ---------------------------------------------------------------------------


class MockQuotaAlertEmailSender(QuotaAlertEmailSender):
    def __init__(self):
        self.calls: list[dict] = []
        self.fail = False

    async def send(
        self, *, to_email, to_name, subject, text_body, html_body
    ):
        self.calls.append({
            "to_email": to_email,
            "to_name": to_name,
            "subject": subject,
        })
        if self.fail:
            raise RuntimeError("mock sender configured to fail")


@pytest.fixture
def ctx():
    return {}


@pytest.fixture(autouse=True)
def _override_sender(app, ctx):
    """每個測試把 quota_alert_email_sender 換成 MockSender（記錄 + 控制失敗）。"""
    mock = MockQuotaAlertEmailSender()
    ctx["mock_sender"] = mock
    container = app.container
    container.quota_alert_email_sender.override(providers.Object(mock))
    yield
    container.quota_alert_email_sender.reset_override()


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("admin 已登入並 seed 三個方案")
def admin_logged_in_and_seed(ctx, client, admin_headers):
    ctx["admin_headers"] = admin_headers
    ctx["tenants"] = {}
    for plan_data in SEED_PLANS:
        resp = client.post(
            "/api/v1/admin/plans", json=plan_data, headers=admin_headers
        )
        if resp.status_code not in (201, 409):
            raise AssertionError(f"plan seed failed: {resp.text}")


@given(parsers.parse('已建立租戶 "{tname}" 綁定 plan "{plan_name}"'))
def create_tenant_with_plan(ctx, client, app, tname, plan_name):
    resp = client.post(
        "/api/v1/tenants",
        json={"name": tname},
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    ctx["tenants"][tname] = tenant_id
    ctx["app"] = app

    assign = client.post(
        f"/api/v1/admin/plans/{plan_name}/assign/{tenant_id}",
        headers=ctx["admin_headers"],
    )
    assert assign.status_code == 204, assign.text


@given(parsers.parse(
    "{tname} 有一筆未寄的 base_warning_80 警示"
))
def seed_unsent_alert(ctx, tname):
    container = ctx["app"].container
    alert_repo = container.quota_alert_log_repository()
    tenant_id = ctx["tenants"][tname]

    async def _seed():
        alert = QuotaAlertLog(
            id=str(uuid4()),
            tenant_id=tenant_id,
            cycle_year_month=current_year_month(),
            alert_type=ALERT_TYPE_BASE_WARNING_80,
            used_ratio=Decimal("0.85"),
            message="Base 額度已用 85.0%",
            delivered_to_email=False,
            created_at=datetime.now(timezone.utc),
        )
        saved = await alert_repo.save_if_new(alert)
        assert saved is not None
        return saved.id

    ctx["alert_id"] = _run(_seed())


@given(parsers.parse(
    '{tname} 有一位 admin 使用者 email "{email}"'
))
def create_admin_user(ctx, client, app, tname, email):
    """直接走 /api/v1/admin/users 建一個 tenant_admin role 的 user。"""
    tenant_id = ctx["tenants"][tname]
    resp = client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "password": "TestPassword123!",
            "role": "tenant_admin",
            "tenant_id": tenant_id,
        },
        headers=ctx["admin_headers"],
    )
    assert resp.status_code == 201, resp.text


@given("mock SendGrid 設定為失敗")
def configure_sender_fail(ctx):
    ctx["mock_sender"].fail = True


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("執行 QuotaEmailDispatchUseCase")
def run_dispatch(ctx):
    container = ctx["app"].container
    use_case = container.quota_email_dispatch_use_case()
    ctx["dispatch_stats"] = _run(use_case.execute())


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("mock SendGrid 應被呼叫 {n:d} 次"))
def verify_sender_call_count(ctx, n):
    actual = len(ctx["mock_sender"].calls)
    assert actual == n, (
        f"expected {n} sender calls, got {actual}: {ctx['mock_sender'].calls}"
    )


@then(parsers.parse('收件者應為 "{email}"'))
def verify_recipient(ctx, email):
    calls = ctx["mock_sender"].calls
    assert len(calls) > 0
    assert calls[0]["to_email"] == email


@then(parsers.parse("該警示 delivered_to_email 應為 {flag}"))
def verify_delivered_flag(ctx, flag):
    expected = flag == "True"
    container = ctx["app"].container
    alert_repo = container.quota_alert_log_repository()
    cycle = current_year_month()
    tenant_id = list(ctx["tenants"].values())[0]

    async def _fetch():
        alerts = await alert_repo.find_by_tenant_and_cycle(tenant_id, cycle)
        return alerts

    alerts = _run(_fetch())
    assert len(alerts) > 0, "no alerts found"
    target = next((a for a in alerts if a.id == ctx["alert_id"]), None)
    assert target is not None, f"alert {ctx['alert_id']} not found"
    assert target.delivered_to_email is expected, (
        f"delivered_to_email expected {expected}, got {target.delivered_to_email}"
    )
