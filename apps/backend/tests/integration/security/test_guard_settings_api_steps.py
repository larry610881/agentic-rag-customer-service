"""防護階段設定 API 整合測試 — BDD Step Definitions（Issue #75）

對證前端（/admin/guard-control、/guard-status、bot 表單「防護階段」）所依賴的契約：
- 租戶 PUT 整列取代：profile / locked 送 null = 刪鍵（非「不變更」）
- 總覽 profiles 已含內建方案；方案 PUT 未知名稱即新增、overrides {} 即沿用
- 租戶 profile 永不為 null（未設定 = standard）
- bot guard_stages 超集 / 鎖定規則；/guard/effective 形狀；租戶端變更紀錄「平台」標記

Feature: tests/features/integration/security/guard_settings_api.feature
"""
from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

# 這幾張表未在 models/__init__ 註冊；先 import 確保 conftest 的 create_all 建表
from src.infrastructure.db.models.audit_log_model import AuditLogModel  # noqa: F401
from src.infrastructure.db.models.guard_settings_model import (  # noqa: F401
    GuardSettingsModel,
)

scenarios("integration/security/guard_settings_api.feature")

ADMIN = "/api/v1/admin/guard/settings"
ALL_STAGES = [
    "regex_input",
    "classifier_attack",
    "output_guard",
    "abuse_scoring",
    "local_classifier",
]
FLOOR = ["regex_input", "output_guard", "abuse_scoring"]


def _stages(text: str) -> list[str]:
    return [s.strip() for s in text.replace("，", "、").split("、") if s.strip()]


@pytest.fixture
def ctx():
    return {}


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("系統管理員已登入")
def admin_login(ctx, admin_headers):
    ctx["admin"] = admin_headers


@given(parsers.parse('已建立租戶 "{name}" 並以 tenant_admin 登入'))
def tenant_login(ctx, app, client, name):
    resp = client.post("/api/v1/tenants", json={"name": name}, headers=ctx["admin"])
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    token = app.container.jwt_service().create_user_token(
        user_id=f"ta-{name}", tenant_id=tenant_id, role="tenant_admin",
    )
    ctx["tenant_id"] = tenant_id
    ctx["tenant"] = {"Authorization": f"Bearer {token}"}


@given(parsers.parse('tenant_admin 已建立 Bot "{name}"'))
def create_bot(ctx, client, name):
    resp = client.post("/api/v1/bots", json={"name": name}, headers=ctx["tenant"])
    assert resp.status_code == 201, resp.text
    ctx["bot"] = resp.json()


# ---------------------------------------------------------------------------
# When — 總覽 / 租戶讀
# ---------------------------------------------------------------------------


@when("系統管理員 GET 防護總覽")
def get_overview(ctx, client):
    ctx["response"] = client.get(ADMIN, headers=ctx["admin"])
    assert ctx["response"].status_code == 200, ctx["response"].text


@when(parsers.parse('系統管理員 GET 租戶 "{name}" 的防護設定'))
def admin_get_tenant(ctx, client, name):
    ctx["response"] = client.get(
        f"{ADMIN}/tenants/{ctx['tenant_id']}", headers=ctx["admin"],
    )
    assert ctx["response"].status_code == 200, ctx["response"].text


@when("tenant_admin GET 自己租戶的防護設定")
def tenant_get_own(ctx, client):
    ctx["response"] = client.get(
        f"{ADMIN}/tenants/{ctx['tenant_id']}", headers=ctx["tenant"],
    )


@when(parsers.parse('tenant_admin GET 租戶 "{other}" 的防護設定'))
def tenant_get_other(ctx, client, other):
    ctx["response"] = client.get(f"{ADMIN}/tenants/{other}", headers=ctx["tenant"])


# ---------------------------------------------------------------------------
# When — 租戶 PUT
# ---------------------------------------------------------------------------


def _put_tenant(ctx, client, body):
    ctx["response"] = client.put(
        f"{ADMIN}/tenants/{ctx['tenant_id']}", json=body, headers=ctx["admin"],
    )


@when(parsers.parse(
    '系統管理員 PUT 租戶 "{name}" 防護 profile "{profile}"、'
    "加開 {stage}、locked {locked}"
))
def put_tenant_full(ctx, client, name, profile, stage, locked):
    _put_tenant(ctx, client, {
        "profile": profile,
        "overrides": {"stages": _stages(stage)},
        "locked": locked == "true",
    })


@when(parsers.parse(
    '系統管理員 PUT 租戶 "{name}" 防護 profile "{profile}"、'
    "overrides 空、locked {locked}"
))
def put_tenant_profile_locked(ctx, client, name, profile, locked):
    _put_tenant(
        ctx, client, {"profile": profile, "overrides": {}, "locked": locked == "true"},
    )


@when(parsers.parse(
    '系統管理員 PUT 租戶 "{name}" 防護 profile null、overrides 空、locked null'
))
def put_tenant_nulls(ctx, client, name):
    _put_tenant(ctx, client, {"profile": None, "overrides": {}, "locked": None})


@when(parsers.parse('系統管理員 PUT 租戶 "{name}" 防護 profile "{profile}"'))
def put_tenant_profile_only(ctx, client, name, profile):
    _put_tenant(ctx, client, {"profile": profile, "overrides": {}, "locked": False})


# ---------------------------------------------------------------------------
# When — 方案 PUT
# ---------------------------------------------------------------------------


def _put_profile(ctx, client, name, overrides):
    ctx["response"] = client.put(
        f"{ADMIN}/profiles/{name}", json={"overrides": overrides}, headers=ctx["admin"],
    )


@when(parsers.parse('系統管理員 PUT 方案 "{name}" stages 為 {stages}'))
def put_profile_stages(ctx, client, name, stages):
    _put_profile(ctx, client, name, {"stages": _stages(stages)})


@when(parsers.parse('系統管理員 PUT 方案 "{name}" overrides 空物件'))
def put_profile_empty(ctx, client, name):
    _put_profile(ctx, client, name, {})


@when(parsers.parse('系統管理員 PUT 方案 "{name}" stages 含未知階段 "{bogus}"'))
def put_profile_bogus(ctx, client, name, bogus):
    _put_profile(ctx, client, name, {"stages": ["regex_input", bogus]})


@when(parsers.parse('系統管理員 PUT 方案 "{name}" overrides 含 required_stages'))
def put_profile_required(ctx, client, name):
    _put_profile(ctx, client, name, {"required_stages": ["regex_input"]})


# ---------------------------------------------------------------------------
# When — bot
# ---------------------------------------------------------------------------


@when(parsers.parse("tenant_admin PUT Bot guard_stages 為 {stages}"))
def put_bot_guard(ctx, client, stages):
    ctx["response"] = client.put(
        f"/api/v1/bots/{ctx['bot']['id']}",
        json={"guard_stages": _stages(stages)},
        headers=ctx["tenant"],
    )


@when("tenant_admin GET Bot 的有效防護")
def get_effective(ctx, client):
    ctx["response"] = client.get(
        f"/api/v1/guard/effective?bot_id={ctx['bot']['id']}", headers=ctx["tenant"],
    )


@when("tenant_admin GET 有效防護但不帶 bot_id")
def get_effective_no_bot(ctx, client):
    ctx["response"] = client.get("/api/v1/guard/effective", headers=ctx["tenant"])


@when("tenant_admin GET Bot 的變更紀錄")
def get_bot_audit(ctx, client):
    ctx["response"] = client.get(
        f"/api/v1/bots/{ctx['bot']['id']}/audit-logs", headers=ctx["tenant"],
    )
    assert ctx["response"].status_code == 200, ctx["response"].text


# ---------------------------------------------------------------------------
# Then — 通用
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態為 {code:d}"))
def status_is(ctx, code):
    assert ctx["response"].status_code == code, ctx["response"].text


@then(parsers.parse('回應狀態為 {code:d} 且 detail 含 "{text}"'))
def status_and_detail(ctx, code, text):
    assert ctx["response"].status_code == code, ctx["response"].text
    assert text in ctx["response"].json()["detail"], ctx["response"].text


@then(parsers.parse('回應狀態為 {code:d} 且 scope_kind 為 "{kind}"'))
def status_and_scope(ctx, code, kind):
    assert ctx["response"].status_code == code, ctx["response"].text
    assert ctx["response"].json()["scope_kind"] == kind


@then(parsers.parse("回應狀態為 {code:d} 且 editable 為 {flag}"))
def status_and_editable(ctx, code, flag):
    assert ctx["response"].status_code == code, ctx["response"].text
    assert ctx["response"].json()["editable"] is (flag == "true")


# ---------------------------------------------------------------------------
# Then — 總覽
# ---------------------------------------------------------------------------


@then("總覽的 profiles 含內建 standard（空）與 exhibition（不含 classifier_attack）")
def overview_builtin_profiles(ctx):
    profiles = ctx["response"].json()["profiles"]
    assert profiles["standard"] == {}
    assert "classifier_attack" not in profiles["exhibition"]["stages"]
    assert set(FLOOR) <= set(profiles["exhibition"]["stages"])


@then("總覽的 builtin_profiles 為 exhibition、standard")
def overview_builtin_names(ctx):
    assert ctx["response"].json()["builtin_profiles"] == ["exhibition", "standard"]


@then(
    "總覽的 effective_default 底線為 regex_input、output_guard、abuse_scoring "
    "且 profile 為 standard"
)
def overview_effective_default(ctx):
    body = ctx["response"].json()
    eff = body["effective_default"]
    assert eff["required"] == FLOOR
    assert eff["profile"] == "standard"
    assert "classifier_attack" in eff["stages"]
    assert eff["source_map"]["classifier_attack"] == "platform"
    assert body["required_floor_default"] == FLOOR


@then("總覽的 stages 為五個可用階段")
def overview_stages(ctx):
    assert ctx["response"].json()["stages"] == ALL_STAGES


@then(parsers.parse('總覽的 profiles 含 "{name}" 且其 stages 有四段'))
def overview_profile_four(ctx, name):
    assert len(ctx["response"].json()["profiles"][name]["stages"]) == 4


@then(parsers.parse('總覽的 profiles 含 "{name}" 且為空覆寫'))
def overview_profile_empty(ctx, name):
    assert ctx["response"].json()["profiles"][name] == {}


# ---------------------------------------------------------------------------
# Then — 租戶
# ---------------------------------------------------------------------------


@then(parsers.parse(
    '租戶設定的 profile 為 "{profile}"、locked 為 {locked}、'
    "overrides 為空、editable 為 {editable}"
))
def tenant_settings_are(ctx, profile, locked, editable):
    body = ctx["response"].json()
    assert body["profile"] == profile
    assert body["locked"] is (locked == "true")
    assert body["overrides"] == {}
    assert body["editable"] is (editable == "true")


@then(parsers.parse(
    "回應狀態為 {code:d} 且 overrides 含 profile {profile}、"
    "locked {locked}、stages {stage}"
))
def saved_overrides_full(ctx, code, profile, locked, stage):
    assert ctx["response"].status_code == code, ctx["response"].text
    ov = ctx["response"].json()["overrides"]
    assert ov["profile"] == profile
    assert ov["locked"] is (locked == "true")
    assert ov["stages"] == _stages(stage)


@then(parsers.parse("回應狀態為 {code:d} 且 overrides 為空"))
def saved_overrides_empty(ctx, code):
    assert ctx["response"].status_code == code, ctx["response"].text
    assert ctx["response"].json()["overrides"] == {}


@then("租戶有效階段含 classifier_attack 且來源為 tenant")
def effective_has_tenant_stage(ctx):
    eff = ctx["response"].json()["effective"]
    assert "classifier_attack" in eff["stages"]
    assert eff["source_map"]["classifier_attack"] == "tenant"
    assert eff["profile"] == "exhibition"


@then("租戶有效階段不含 classifier_attack 且 locked 為 true")
def effective_ignores_when_locked(ctx):
    body = ctx["response"].json()
    assert body["locked"] is True
    assert body["effective"]["locked"] is True
    assert "classifier_attack" not in body["effective"]["stages"]


# ---------------------------------------------------------------------------
# Then — bot
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態為 {code:d} 且 Bot 的 guard_stages 有五段"))
def bot_guard_five(ctx, code):
    assert ctx["response"].status_code == code, ctx["response"].text
    assert ctx["response"].json()["guard_stages"] == ALL_STAGES


@then(
    "有效防護含 tenant_id、bot_id、五個 available_stages，"
    "且 local_classifier 來源為 bot"
)
def effective_view_shape(ctx):
    assert ctx["response"].status_code == 200, ctx["response"].text
    body = ctx["response"].json()
    assert body["tenant_id"] == ctx["tenant_id"]
    assert body["bot_id"] == ctx["bot"]["id"]
    assert body["available_stages"] == ALL_STAGES
    assert body["bot_stages"] == ALL_STAGES
    assert body["source_map"]["local_classifier"] == "bot"
    assert body["source_map"]["regex_input"] == "required"
    assert body["required"] == FLOOR
    assert body["locked"] is False
    assert body["profile"] == "standard"


@then(parsers.parse('變更紀錄含一筆 entity_type guard_settings、actor_label "{label}"'))
def audit_has_platform_entry(ctx, label):
    items = ctx["response"].json()["items"]
    guard = [i for i in items if i.get("entity_type") == "guard_settings"]
    assert guard, items
    assert guard[0]["actor_label"] == label
    assert guard[0]["source"] == "platform"
