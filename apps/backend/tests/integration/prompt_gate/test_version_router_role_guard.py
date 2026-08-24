"""Regression: config-version 寫入端點限管理員角色（H4）。

一般成員 role="user"（註冊預設）不得建立/發布/回朔版本或觸發 validate/replay
（租戶內權限提升 + 燒 gate_daily_limit）。tenant_admin / system_admin 可。
"""


def _hdr(app, tenant_id, role):
    token = app.container.jwt_service().create_user_token(
        user_id=f"u-{role}", tenant_id=tenant_id, role=role
    )
    return {"Authorization": f"Bearer {token}"}


def _make_tenant_bot(client, app):
    admin = _hdr(app, None, "system_admin")
    resp = client.post("/api/v1/tenants", json={"name": "role-t"}, headers=admin)
    assert resp.status_code == 201, resp.text
    tid = resp.json()["id"]
    bot = client.post(
        "/api/v1/bots", json={"name": "b"}, headers=_hdr(app, tid, "tenant_admin")
    )
    assert bot.status_code == 201, bot.text
    return tid, bot.json()["id"]


def test_user_role_forbidden_on_version_writes(client, app):
    tid, bot_id = _make_tenant_bot(client, app)
    user = _hdr(app, tid, "user")
    base = f"/api/v1/bots/{bot_id}/config-versions"

    # 6 個寫入/驗證端點對 role=user 一律 403（在 use case 之前就擋）
    assert client.post(
        base, json={"changes": {"base_prompt": "x"}}, headers=user
    ).status_code == 403
    assert client.post(
        f"{base}/some-id/publish", headers=user
    ).status_code == 403
    assert client.post(
        f"{base}/some-id/reject", headers=user
    ).status_code == 403
    assert client.post(
        base + "/rollback",
        json={"target_version_id": "x"},
        headers=user,
    ).status_code == 403
    assert client.post(
        f"{base}/some-id/validate", headers=user
    ).status_code == 403
    assert client.post(
        f"{base}/some-id/replay-compare", headers=user
    ).status_code == 403


def test_user_role_can_still_read_versions(client, app):
    tid, bot_id = _make_tenant_bot(client, app)
    user = _hdr(app, tid, "user")
    # GET 列表對一般成員維持可讀
    listing = client.get(
        f"/api/v1/bots/{bot_id}/config-versions", headers=user
    )
    assert listing.status_code == 200, listing.text


def test_tenant_admin_can_create_version(client, app):
    tid, bot_id = _make_tenant_bot(client, app)
    admin = _hdr(app, tid, "tenant_admin")
    resp = client.post(
        f"/api/v1/bots/{bot_id}/config-versions",
        json={"changes": {"base_prompt": "管理員版"}},
        headers=admin,
    )
    assert resp.status_code == 201, resp.text
