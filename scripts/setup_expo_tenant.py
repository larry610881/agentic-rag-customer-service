#!/usr/bin/env python3
"""建立「3D 虛擬商品展」租戶與知識庫（LumineAI 備案評測用）。

跟 `setup_eval_tenant.py` 的差別，以及為什麼要獨立一個租戶：

- **不能沿用「模型評測」租戶**：那邊的 bot 綁著 FAQ + DM 兩個知識庫，多塞一個秋季展 KM
  會污染檢索；限流與異常控管也是按租戶算的，共用會讓兩邊的測試互相干擾。
- **`ocr_slice_grid` 留空**：切片 OCR 是為 DM 的密集商品格設計的（2x3 切片讓罕用字的
  像素占比變高）。簡報是 16:9 單一主題頁，切片只會把一張圖切成兩半、產生「半個內容」
  的雜訊。

冪等：每步先查再建，重跑不重複。

用法：
  ADMIN_PASSWORD=... EXPO_ADMIN_PASSWORD=... python3 scripts/setup_expo_tenant.py \\
      --base-url https://agentic-rag-969010424468.asia-east1.run.app
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def call(base, tok, method, path, body=None, ok=(200, 201, 202, 204)):
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=json.dumps(body).encode() if body is not None else None, method=method,
    )
    req.add_header("Content-Type", "application/json")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw, st = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, st = e.read(), e.code
    payload = json.loads(raw) if raw else None
    if st not in ok:
        raise RuntimeError(f"{method} {path} -> {st}: {str(payload)[:300]}")
    return payload


def items(payload):
    return payload if isinstance(payload, list) else (payload or {}).get("items", [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--admin-account", default="admin@system.com")
    ap.add_argument("--tenant-name", default="3D虛擬商品展")
    ap.add_argument("--tenant-admin-email", default="expo-admin@example.com")
    ap.add_argument("--kb-name", default="秋季展KM")
    ap.add_argument("--ocr-model", default="google:gemini-3.8-flash")
    ap.add_argument("--abuse-profile", default="monitor")
    ap.add_argument("--guard-profile", default="exhibition")
    args = ap.parse_args()

    admin_pw = os.environ.get("ADMIN_PASSWORD")
    expo_pw = os.environ.get("EXPO_ADMIN_PASSWORD")
    if not admin_pw or not expo_pw:
        print("請以環境變數提供 ADMIN_PASSWORD 與 EXPO_ADMIN_PASSWORD")
        return 2

    base = args.base_url
    admin = call(base, None, "POST", "/api/v1/auth/login",
                 {"account": args.admin_account, "password": admin_pw})["access_token"]

    tenant = next(
        (t for t in items(call(base, admin, "GET", "/api/v1/tenants?page=1&page_size=200"))
         if t.get("name") == args.tenant_name), None)
    if tenant:
        print(f"==> 租戶已存在：{args.tenant_name}（{tenant['id']}）")
    else:
        tenant = call(base, admin, "POST", "/api/v1/tenants",
                      {"name": args.tenant_name, "plan": "starter"})
        print(f"==> 建立租戶：{args.tenant_name}（{tenant['id']}）")
    tid = tenant["id"]

    call(base, admin, "PUT", f"/api/v1/admin/abuse/settings/tenants/{tid}",
         {"profile": args.abuse_profile, "overrides": {}})
    call(base, admin, "PUT", f"/api/v1/admin/guard/settings/tenants/{tid}",
         {"profile": args.guard_profile, "overrides": {}, "locked": False})
    print(f"==> 異常控管={args.abuse_profile}、防護方案={args.guard_profile}")

    try:
        call(base, admin, "POST", "/api/v1/admin/users",
             {"email": args.tenant_admin_email, "password": expo_pw,
              "role": "tenant_admin", "tenant_id": tid})
        print(f"==> 建立 tenant_admin：{args.tenant_admin_email}")
    except RuntimeError as e:
        if any(x in str(e) for x in ("409", "400", "exists", "已存在")):
            print(f"==> tenant_admin 已存在：{args.tenant_admin_email}")
        else:
            raise

    tok = call(base, None, "POST", "/api/v1/auth/login",
               {"account": args.tenant_admin_email, "password": expo_pw})["access_token"]

    kb = next((k for k in items(call(base, tok, "GET",
                                     "/api/v1/knowledge-bases?page=1&page_size=200"))
               if k.get("name") == args.kb_name), None)
    if kb:
        print(f"==> 知識庫已存在：{args.kb_name}（{kb['id']}）")
    else:
        kb = call(base, tok, "POST", "/api/v1/knowledge-bases", {
            "name": args.kb_name,
            "description": "2026 秋季商品展簡報（pptx 轉 PDF）",
            "ocr_mode": "auto",
            "ocr_model": args.ocr_model,
            # 刻意留空：切片是為 DM 密集商品格設計的，簡報單主題頁切了只會產生半截內容
            "ocr_slice_grid": "",
        })
        print(f"==> 建立知識庫：{args.kb_name}（{kb['id']}）")

    print("\n=== 交付資訊 ===")
    print(f"  租戶        {args.tenant_name}　{tid}")
    print(f"  tenant_admin {args.tenant_admin_email}")
    print(f"  知識庫      {args.kb_name}　{kb['id']}")
    print(f"\n上傳指令（每個 PDF 一次；不要走後台 UI，該桶 CORS 未設）：")
    print(f"  TOKEN=$(curl -s -X POST {base}/api/v1/auth/login \\")
    print(f"    -H 'Content-Type: application/json' \\")
    print(f"    -d '{{\"account\":\"{args.tenant_admin_email}\",\"password\":\"<密碼>\"}}' \\")
    print(f"    | python3 -c 'import sys,json;print(json.load(sys.stdin)[\"access_token\"])')")
    print(f"  curl -X POST '{base}/api/v1/knowledge-bases/{kb['id']}/documents' \\")
    print(f"    -H \"Authorization: Bearer $TOKEN\" -F 'file=@<檔名>.pdf'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
