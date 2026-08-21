"""Regression: bot 端點跨租戶存取一律 404（C8/C9，端點級防線）。

租戶 A 建 bot，租戶 B 以自己的 JWT 對該 bot 發 GET/PUT/DELETE → 全部 404，
不得讀取（含 LINE 憑證）、竄改或刪除。釘住 bot_router 有把 tenant/role 帶進 use case。
"""


def _auth_only(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


def test_cross_tenant_bot_access_is_404(client, create_tenant_login):
    owner = _auth_only(create_tenant_login("owner-tenant"))
    attacker = _auth_only(create_tenant_login("attacker-tenant"))

    created = client.post(
        "/api/v1/bots", json={"name": "owner-bot"}, headers=owner
    )
    assert created.status_code == 201, created.text
    bot_id = created.json()["id"]

    # 攻擊者讀取 → 404（不洩漏存在性與 LINE 憑證）
    got = client.get(f"/api/v1/bots/{bot_id}", headers=attacker)
    assert got.status_code == 404, got.text

    # 攻擊者竄改 → 404
    put = client.put(
        f"/api/v1/bots/{bot_id}",
        json={"base_prompt": "hijacked"},
        headers=attacker,
    )
    assert put.status_code == 404, put.text

    # 攻擊者刪除 → 404
    deleted = client.delete(f"/api/v1/bots/{bot_id}", headers=attacker)
    assert deleted.status_code == 404, deleted.text

    # 擁有者仍可正常讀取
    owner_get = client.get(f"/api/v1/bots/{bot_id}", headers=owner)
    assert owner_get.status_code == 200, owner_get.text
    assert owner_get.json()["base_prompt"] != "hijacked"
