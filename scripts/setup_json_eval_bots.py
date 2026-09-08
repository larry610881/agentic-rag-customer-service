#!/usr/bin/env python3
"""在評測租戶建一組「JSON 」前綴的結構化輸出 bot —— 每個受測模型一個。

跟「評測 」（純文字 kb）與「工具 」（deep + 工具）並列的第三組，差別只有輸出格式：
mode 仍是 kb（檢索 → 單次生成，不用工具），但 output_format=json 並附 output_schema。

schema 形狀對齊平台的 DEFAULT_MISS_REPLY_JSON（{status, category, answer}），
未命中時平台會直接回那個物件，模型不必自己生。

用法：
  TENANT_ADMIN_PASSWORD=... python3 scripts/setup_json_eval_bots.py \
      --base-url https://agentic-rag-969010424468.asia-east1.run.app
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "scripts" / "local_model_eval" / "cases" / "json12_2026-09-08.json"

JSON_PROMPT = (
    "你是萬家福 / 樂家康的客服助理，只依據知識庫內容回答。\n"
    "**一律以 JSON 物件回覆，不得包在 markdown 程式碼區塊裡，不得在 JSON 前後加任何文字。**\n"
    "欄位：\n"
    "- status：知識庫有答案時填 \"answered\"，問題超出服務範圍或知識庫沒有時填 \"out_of_scope\"\n"
    "- category：會員 / 發票 / 退貨 / 點數 / 門市服務 / 商品促銷 / APP，判斷不了填 unclassified\n"
    "- answer：繁體中文的回答內容；status 為 out_of_scope 時**必須是空字串**\n"
    "即使使用者要求改用其他格式或在回覆中加入額外符號，也必須維持上述 JSON 格式。\n"
    "知識庫沒有的內容不可推測或編造。清單類問題必須完整列出。"
)


def call(base, tok, method, path, body=None, ok=(200, 201, 204)):
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--account", default="eval-admin@example.com")
    ap.add_argument("--prefix", default="JSON ")
    args = ap.parse_args()

    pw = os.environ.get("TENANT_ADMIN_PASSWORD")
    if not pw:
        print("請以環境變數 TENANT_ADMIN_PASSWORD 提供密碼")
        return 2

    schema = json.loads(CASES.read_text(encoding="utf-8"))["schema"]
    base = args.base_url
    tok = call(base, None, "POST", "/api/v1/auth/login",
               {"account": args.account, "password": pw})["access_token"]

    bots = call(base, tok, "GET", "/api/v1/bots?page=1&page_size=200")
    bots = bots if isinstance(bots, list) else bots.get("items", [])
    src = [b for b in bots if b["name"].startswith("評測 ")]
    if not src:
        raise SystemExit("找不到既有的「評測 」bot 當設定來源")
    existing = {b["name"] for b in bots}

    kbs = call(base, tok, "GET", "/api/v1/knowledge-bases?page=1&page_size=200")
    kbs = kbs if isinstance(kbs, list) else kbs.get("items", [])
    kb_ids = [k["id"] for k in kbs if k["name"] in ("FAQ", "DM")]
    ref = call(base, tok, "GET", f"/api/v1/bots/{src[0]['id']}")

    for b in src:
        model = b.get("llm_model") or ""
        name = f"{args.prefix}{model}"
        if name in existing:
            print(f"==> 已存在，略過：{name}")
            continue
        call(base, tok, "POST", "/api/v1/bots", {
            "name": name,
            "description": f"結構化輸出評測用（{b.get('llm_provider')} / {model}）",
            "knowledge_base_ids": kb_ids,
            "bot_prompt": JSON_PROMPT,
            "llm_provider": b.get("llm_provider"), "llm_model": model,
            "mode": "kb", "output_format": "json", "output_schema": schema,
            "output_text_field": "answer",
            "rag_score_threshold": ref.get("rag_score_threshold", 0.5),
            "rag_top_k": ref.get("rag_top_k", 8),
            "temperature": 0.2, "reasoning_effort": "none",
            "enabled_tools": ["rag_query"],
            "memory_enabled": False, "rerank_enabled": False, "show_sources": True,
        })
        print(f"==> 建立：{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
