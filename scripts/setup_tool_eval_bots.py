#!/usr/bin/env python3
"""在評測租戶建一組「工具評測」bot —— 每個受測模型一個。

跟既有的「評測 」bot 的差別，以及為什麼不能沿用：

1. 既有的是 ``kb`` 模式，**工具集是空的**，一次 function call 都不會發生。
2. 工具 bot 必須 **一個 worker 都不設**。設了 worker，路由是交給 ``router_model``
   （獨立的分類器模型）決定的（send_message_use_case.py:792），受測模型根本沒參與，
   五個臂會得到幾乎一樣的結果。
3. 用 ``deep`` 而非 ``fast``：fast 會把 max_tool_calls 壓到 2
   （send_message_use_case.py:1729），單輪多工具與「先查再轉人」的情境測不出來。

冪等：同名 bot 已存在就略過。

用法：
  TENANT_ADMIN_PASSWORD=... python3 scripts/setup_tool_eval_bots.py \\
      --base-url https://agentic-rag-969010424468.asia-east1.run.app \\
      --account eval-admin@example.com
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

TOOL_PROMPT = (
    "你是萬家福 / 樂家康的客服助理，用繁體中文、精簡扼要回答，先講結論再補條件。\n"
    "你有以下工具可用，請依問題性質選擇：\n"
    "- 一般政策、會員、發票、退貨、APP 等問題 → 用知識庫查詢。\n"
    "- 促銷、特價、折扣、買一送一、商品價格、當期 DM → 用 DM 圖卡查詢。\n"
    "- 使用者明確要求真人、情緒激烈、或屬於帳務核對這類知識庫處理不了的個人議題 "
    "→ 轉接真人客服。\n"
    "打招呼、道別、閒聊或明顯超出客服範圍的要求，直接回應即可，不需要呼叫任何工具。\n"
    "知識庫沒有的內容不可推測或編造。清單類問題必須完整列出，不可省略。"
)

CUSTOMER_SERVICE_URL = "https://www.uni-prosperity.com.tw/contact-us/"
TOOLS = ["rag_query", "query_dm_with_image", "transfer_to_human_agent"]


def call(base, tok, method, path, body=None, ok=(200, 201, 204)):
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
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
    ap.add_argument("--prefix", default="工具 ")
    args = ap.parse_args()

    pw = os.environ.get("TENANT_ADMIN_PASSWORD")
    if not pw:
        print("請以環境變數 TENANT_ADMIN_PASSWORD 提供密碼")
        return 2

    base = args.base_url
    tok = call(base, None, "POST", "/api/v1/auth/login",
               {"account": args.account, "password": pw})["access_token"]

    bots = call(base, tok, "GET", "/api/v1/bots?page=1&page_size=200")
    bots = bots if isinstance(bots, list) else bots.get("items", [])
    kb_bots = [b for b in bots if b["name"].startswith("評測 ")]
    if not kb_bots:
        raise SystemExit("找不到既有的「評測 」bot 當設定來源")
    existing = {b["name"] for b in bots}

    kbs = call(base, tok, "GET", "/api/v1/knowledge-bases?page=1&page_size=200")
    kbs = kbs if isinstance(kbs, list) else kbs.get("items", [])
    kb_ids = [k["id"] for k in kbs if k["name"] in ("FAQ", "DM")]
    if len(kb_ids) != 2:
        raise SystemExit(f"知識庫不齊：{[k['name'] for k in kbs]}")

    # router_model 五個臂統一，避免防護用的攻擊判定成為額外變因
    ref = call(base, tok, "GET", f"/api/v1/bots/{kb_bots[0]['id']}")
    router_model = ref.get("router_model") or ""

    for b in kb_bots:
        model = b.get("llm_model") or ""
        name = f"{args.prefix}{model}"
        if name in existing:
            print(f"==> 已存在，略過：{name}")
            continue
        call(base, tok, "POST", "/api/v1/bots", {
            "name": name,
            "description": f"工具呼叫評測用（{b.get('llm_provider')} / {model}）",
            "knowledge_base_ids": kb_ids,
            "bot_prompt": TOOL_PROMPT,
            "llm_provider": b.get("llm_provider"),
            "llm_model": model,
            "mode": "deep",
            "output_format": "text",
            "rag_score_threshold": ref.get("rag_score_threshold", 0.5),
            "rag_top_k": ref.get("rag_top_k", 8),
            "temperature": 0.2,
            "reasoning_effort": "none",
            "enabled_tools": TOOLS,
            "max_tool_calls": 5,
            "customer_service_url": CUSTOMER_SERVICE_URL,
            "router_model": router_model,
            "memory_enabled": False,
            "rerank_enabled": False,
            "show_sources": True,
        })
        print(f"==> 建立：{name}")

    after = call(base, tok, "GET", "/api/v1/bots?page=1&page_size=200")
    after = after if isinstance(after, list) else after.get("items", [])
    print("\n目前工具評測 bot：")
    for b in after:
        if b["name"].startswith(args.prefix):
            print(f"  {b['id']}  {b['name']}  {b.get('llm_provider')}/{b.get('llm_model')}")
    print("\n提醒：query_dm_with_image 需要 GCS 權限才回得了圖（子頁 PNG 的 storage_path "
          "目前是空的）。工具**選擇**仍可正常評分，只有 DM 題的最終回答會受影響。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
