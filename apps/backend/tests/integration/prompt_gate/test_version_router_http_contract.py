"""Regression: config-version router HTTP 契約 401/404/422（H20，review 標為零覆蓋）。"""


def _admin(app, tenant_id):
    token = app.container.jwt_service().create_user_token(
        user_id="ta", tenant_id=tenant_id, role="tenant_admin"
    )
    return {"Authorization": f"Bearer {token}"}


def _make_bot(client, app):
    admin0 = app.container.jwt_service().create_user_token(
        user_id="a", tenant_id=None, role="system_admin"
    )
    resp = client.post(
        "/api/v1/tenants", json={"name": "cv-http"},
        headers={"Authorization": f"Bearer {admin0}"},
    )
    assert resp.status_code == 201, resp.text
    tid = resp.json()["id"]
    bot = client.post(
        "/api/v1/bots", json={"name": "b"}, headers=_admin(app, tid)
    )
    assert bot.status_code == 201, bot.text
    return tid, bot.json()["id"]


def test_list_versions_requires_auth(client):
    resp = client.get("/api/v1/bots/bot-x/config-versions")
    assert resp.status_code == 401, resp.text


def test_get_nonexistent_version_404(client, app):
    tid, bot_id = _make_bot(client, app)
    resp = client.get(
        f"/api/v1/bots/{bot_id}/config-versions/nope",
        headers=_admin(app, tid),
    )
    assert resp.status_code == 404, resp.text


def test_create_version_missing_changes_422(client, app):
    tid, bot_id = _make_bot(client, app)
    resp = client.post(
        f"/api/v1/bots/{bot_id}/config-versions",
        json={},  # 缺 changes（必填）
        headers=_admin(app, tid),
    )
    assert resp.status_code == 422, resp.text


def test_publish_nonexistent_version_404(client, app):
    tid, bot_id = _make_bot(client, app)
    resp = client.post(
        f"/api/v1/bots/{bot_id}/config-versions/nope/publish",
        headers=_admin(app, tid),
    )
    assert resp.status_code == 404, resp.text


def test_create_version_non_whitelist_field_400(client, app):
    tid, bot_id = _make_bot(client, app)
    resp = client.post(
        f"/api/v1/bots/{bot_id}/config-versions",
        json={"changes": {"not_a_versioned_field": "x"}},
        headers=_admin(app, tid),
    )
    assert resp.status_code == 400, resp.text
