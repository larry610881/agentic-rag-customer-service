"""Regression: /datasets/import 非 admin 不得冒名指定 tenant_id（H12）。"""

_YAML = """schema_version: "1.0"
metadata:
  description: "imported"
test_cases:
  - id: "c1"
    question: "hi"
    priority: "P1"
"""


def _auth_only(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


def test_import_ignores_foreign_tenant_id_for_non_admin(
    client, create_tenant_login
):
    a = create_tenant_login("imp-a")
    b = create_tenant_login("imp-b")
    a_id, b_id = a["_tenant_id"], b["_tenant_id"]
    base = "/api/v1/prompt-optimizer"

    resp = client.post(
        f"{base}/datasets/import",
        json={"yaml_content": _YAML, "tenant_id": b_id},
        headers=_auth_only(a),
    )
    assert resp.status_code == 201, resp.text
    # 應歸屬於 A（呼叫者），而非 body 指定的 B
    assert resp.json()["tenant_id"] == a_id

    # B 的題集列表不應出現這筆
    b_list = client.get(f"{base}/datasets", headers=_auth_only(b))
    assert b_list.status_code == 200
    assert all(d["tenant_id"] == b_id for d in b_list.json()["items"])
