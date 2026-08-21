"""Regression: eval dataset 端點跨租戶隔離與平台集讀寫切分（C4–C7，端點級）。

- 租戶 A 建 dataset，租戶 B 對其 GET/export/PUT/DELETE/建 case/eval → 全 404。
- 平台通用集：非擁有者可讀（GET 200），但寫入（PUT / 建 case）→ 403。
"""


def _auth_only(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


def _create_dataset(client, headers, name="ds"):
    resp = client.post(
        "/api/v1/prompt-optimizer/datasets",
        json={"name": name},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_cross_tenant_dataset_endpoints_are_404(
    client, create_tenant_login
):
    owner = _auth_only(create_tenant_login("ds-owner"))
    attacker = _auth_only(create_tenant_login("ds-attacker"))
    ds_id = _create_dataset(client, owner)
    base = "/api/v1/prompt-optimizer"
    ds = f"{base}/datasets/{ds_id}"

    assert client.get(ds, headers=attacker).status_code == 404
    assert client.get(f"{ds}/export", headers=attacker).status_code == 404
    assert client.put(
        ds, json={"name": "hijack"}, headers=attacker
    ).status_code == 404
    assert client.post(
        f"{ds}/cases",
        json={"case_id": "c1", "question": "q"},
        headers=attacker,
    ).status_code == 404
    assert client.post(
        f"{base}/eval", json={"dataset_id": ds_id}, headers=attacker
    ).status_code == 404
    # 刪除放最後（避免影響上面）：跨租戶刪 → 404，且 owner 仍讀得到
    assert client.delete(ds, headers=attacker).status_code == 404
    assert client.get(ds, headers=owner).status_code == 200


def test_platform_base_readable_but_not_writable_by_non_admin(
    client, create_tenant_login, admin_headers
):
    owner = _auth_only(create_tenant_login("pb-owner"))
    outsider = _auth_only(create_tenant_login("pb-outsider"))
    base = "/api/v1/prompt-optimizer"
    ds_id = _create_dataset(client, owner, name="platform-set")

    # admin 標記為平台通用集
    marked = client.put(
        f"{base}/datasets/{ds_id}",
        json={"is_platform_base": True},
        headers=admin_headers,
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["is_platform_base"] is True

    # 非擁有者可讀（平台集設計上共享）
    assert client.get(f"{base}/datasets/{ds_id}", headers=outsider).status_code == 200
    # 但不可改 / 不可加 case（403，非 404 — 它知道存在）
    assert client.put(
        f"{base}/datasets/{ds_id}", json={"name": "x"}, headers=outsider
    ).status_code == 403
    assert client.post(
        f"{base}/datasets/{ds_id}/cases",
        json={"case_id": "c1", "question": "q"},
        headers=outsider,
    ).status_code == 403
