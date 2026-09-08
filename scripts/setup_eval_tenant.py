#!/usr/bin/env python3
"""建立「模型評測」租戶：租戶 + 防護/異常控管方案 + tenant_admin + 兩個知識庫 + FAQ 匯入 + 每模型一個 bot。

冪等：每步先查再建，重跑不重複。走 REST API（system_admin 登入建租戶與使用者，
再以 tenant_admin 登入建知識庫 / 匯 FAQ / 建 bot，因為這些端點以呼叫者租戶為準）。

用法（POC）：
  ADMIN_PASSWORD=... TENANT_ADMIN_PASSWORD=... python3 scripts/setup_eval_tenant.py \
      --base-url https://agentic-rag-969010424468.asia-east1.run.app \
      --models google:gemini-3.8-flash,anthropic:claude-sonnet-4-6 \
      --ocr-model google:gemini-3.8-flash

不做的事（請在後台手動）：供應商 API key、上傳 DM PDF（知識庫「DM」）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_FAQ = REPO / "scripts" / "uni-prosperity-faq-data.json"

BOT_PROMPT = (
    "你是萬家福 / 樂家康的客服助理，只依據知識庫內容回答，用繁體中文、精簡扼要，"
    "先講結論再補條件。知識庫沒有的內容不可推測或編造，請禮貌說明無法回答並引導聯絡客服。"
    "清單類問題（門市、分店、服務據點）必須完整列出，不可省略。"
)


class Api:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.token: str | None = None

    def call(self, method: str, path: str, body: dict | None = None, *, ok=(200, 201, 202, 204)):
        url = self.base + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as e:
            raw = e.read()
            status = e.code
        payload = json.loads(raw) if raw else None
        if status not in ok:
            raise RuntimeError(f"{method} {path} -> {status}: {str(payload)[:300]}")
        return payload

    def login(self, account: str, password: str) -> None:
        r = self.call("POST", "/api/v1/auth/login", {"account": account, "password": password})
        self.token = r["access_token"]

    def items(self, path: str) -> list[dict]:
        r = self.call("GET", path)
        if isinstance(r, list):
            return r
        return r.get("items", [])


def step(msg: str) -> None:
    print(f"==> {msg}", flush=True)


def ensure_tenant(admin: Api, name: str) -> dict:
    for t in admin.items("/api/v1/tenants?page=1&page_size=200"):
        if t.get("name") == name:
            step(f"租戶已存在：{name}（{t['id']}）")
            return t
    t = admin.call("POST", "/api/v1/tenants", {"name": name, "plan": "starter"})
    step(f"建立租戶：{name}（{t['id']}）")
    return t


def set_profiles(admin: Api, tenant_id: str, abuse_profile: str, guard_profile: str) -> None:
    admin.call(
        "PUT", f"/api/v1/admin/abuse/settings/tenants/{tenant_id}",
        {"profile": abuse_profile, "overrides": {}},
    )
    admin.call(
        "PUT", f"/api/v1/admin/guard/settings/tenants/{tenant_id}",
        {"profile": guard_profile, "overrides": {}, "locked": False},
    )
    step(f"異常控管方案={abuse_profile}、防護階段方案={guard_profile}")


def ensure_tenant_admin(admin: Api, tenant_id: str, email: str, password: str) -> None:
    try:
        admin.call(
            "POST", "/api/v1/admin/users",
            {"email": email, "password": password, "role": "tenant_admin", "tenant_id": tenant_id},
        )
        step(f"建立 tenant_admin：{email}")
    except RuntimeError as e:
        if "409" in str(e) or "已存在" in str(e) or "exists" in str(e).lower() or "400" in str(e):
            step(f"tenant_admin 已存在：{email}")
        else:
            raise


def ensure_kb(tenant: Api, name: str, **fields) -> dict:
    for kb in tenant.items("/api/v1/knowledge-bases?page=1&page_size=200"):
        if kb.get("name") == name:
            step(f"知識庫已存在：{name}（{kb['id']}）")
            return kb
    kb = tenant.call("POST", "/api/v1/knowledge-bases", {"name": name, **fields})
    step(f"建立知識庫：{name}（{kb['id']}）")
    return kb


def import_faq(tenant: Api, kb_id: str, faq_path: Path, batch: int = 50) -> int:
    existing = tenant.items(f"/api/v1/knowledge-bases/{kb_id}/documents?page=1&page_size=500")
    have = {d.get("filename") or d.get("name") for d in existing}
    data = json.loads(faq_path.read_text(encoding="utf-8"))
    docs: list[dict] = []
    for cat in data:
        category = cat.get("category", "未分類")
        for i, it in enumerate(cat.get("items", []), 1):
            filename = f"{category}/{i:03d}.txt"
            if filename in have:
                continue
            docs.append({
                "content": f"【分類】{category}\n【問題】{it.get('question','')}\n【回答】{it.get('answer','')}",
                "filename": filename,
                "metadata": {"category": category, "source": faq_path.name},
            })
    if not docs:
        step(f"FAQ 已全部匯入（既有 {len(have)} 份），略過")
        return 0
    sent = 0
    for k in range(0, len(docs), batch):
        chunk = docs[k:k + batch]
        r = tenant.call("POST", f"/api/v1/knowledge-bases/{kb_id}/documents/bulk", {"documents": chunk})
        results = r.get("results", r) if isinstance(r, dict) else r
        failed = [x for x in (results or []) if isinstance(x, dict) and x.get("status") == "failed"]
        sent += len(chunk) - len(failed)
        if failed:
            print(f"   失敗 {len(failed)} 份，例如 {failed[0]}")
        time.sleep(0.5)
    step(f"FAQ 匯入 {sent} 份（背景處理中，後台可看進度）")
    return sent


def ensure_bots(tenant: Api, kb_ids: list[str], models: list[str], threshold: float) -> None:
    existing = {b.get("name") for b in tenant.items("/api/v1/bots?page=1&page_size=200")}
    for spec in models:
        provider, _, model = spec.partition(":")
        if not model:
            raise SystemExit(f"--models 格式須為 provider:model，收到 {spec!r}")
        name = f"評測 {model}"
        if name in existing:
            step(f"bot 已存在：{name}")
            continue
        tenant.call("POST", "/api/v1/bots", {
            "name": name,
            "description": f"模型評測用（{provider} / {model}）",
            "knowledge_base_ids": kb_ids,
            "bot_prompt": BOT_PROMPT,
            "llm_provider": provider,
            "llm_model": model,
            "mode": "kb",
            "output_format": "text",
            "rag_score_threshold": threshold,
            "rag_top_k": 8,
            "temperature": 0.2,
            "reasoning_effort": "none",
            "enabled_tools": ["rag_query"],
            "memory_enabled": False,
            "rerank_enabled": False,
            "show_sources": True,
        })
        step(f"建立 bot：{name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--admin-account", default="admin@system.com")
    ap.add_argument("--tenant-name", default="模型評測")
    ap.add_argument("--tenant-admin-email", default="eval-admin@example.com")
    ap.add_argument("--models", default="google:gemini-3.8-flash")
    ap.add_argument("--ocr-model", default="google:gemini-3.8-flash")
    ap.add_argument("--faq", default=str(DEFAULT_FAQ))
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--abuse-profile", default="monitor")
    ap.add_argument("--guard-profile", default="exhibition")
    args = ap.parse_args()

    admin_pw = os.environ.get("ADMIN_PASSWORD")
    ta_pw = os.environ.get("TENANT_ADMIN_PASSWORD")
    if not admin_pw or not ta_pw:
        print("請以環境變數提供 ADMIN_PASSWORD 與 TENANT_ADMIN_PASSWORD（不要寫進指令列或檔案）")
        return 2

    admin = Api(args.base_url)
    admin.login(args.admin_account, admin_pw)
    step(f"system_admin 登入 {args.base_url}")

    tenant_row = ensure_tenant(admin, args.tenant_name)
    tid = tenant_row["id"]
    set_profiles(admin, tid, args.abuse_profile, args.guard_profile)
    ensure_tenant_admin(admin, tid, args.tenant_admin_email, ta_pw)

    tenant = Api(args.base_url)
    tenant.login(args.tenant_admin_email, ta_pw)
    step(f"tenant_admin 登入：{args.tenant_admin_email}")

    kb_faq = ensure_kb(tenant, "FAQ", description="萬家福 / 樂家康官方 FAQ", ocr_mode="general")
    kb_dm = ensure_kb(
        tenant, "DM", description="當期 DM 商品頁（OCR 測試）",
        ocr_mode="auto", ocr_model=args.ocr_model, ocr_slice_grid="2x3",
    )
    import_faq(tenant, kb_faq["id"], Path(args.faq))
    ensure_bots(tenant, [kb_faq["id"], kb_dm["id"]], [m.strip() for m in args.models.split(",") if m.strip()], args.threshold)

    print()
    print("完成。接下來請在後台手動：")
    print(f"  1. 供應商設定填 API key 並啟用模型（{args.models}）")
    print(f"  2. 以 {args.tenant_admin_email} 登入，知識庫「DM」上傳 Downloads/DM_家樂福_采集漫旅_2026-09-01/DM_家樂福_采集漫旅_商品頁_p11-15.pdf")
    print("  3. 依 scripts/local_model_eval/cases/quick20_2026-09-08.md 逐 bot 跑 20 題")
    return 0


if __name__ == "__main__":
    sys.exit(main())
