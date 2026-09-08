#!/usr/bin/env python3
"""把 agent trace 拆成分段耗時，依模型彙整 —— 給模型性價比比較用。

為什麼不用客戶端計時：客戶端只量得到「總時間」與「首 token」，中間混了網路來回、
檢索、prompt 組裝、模型 prefill，拆不開。trace 的 start_ms / end_ms 是**伺服器端**
的相對時間，每個請求本來就在存，拿來拆段既精準又不用改任何線上程式。

分段定義（全部取自 trace 節點）：

    request ├─ 前置    ：對話載入 + Bot 設定載入 + 防護階段
            ├─ 檢索    ├─ Embedding      （embed_query，打 embedding 供應商）
            │          └─ 向量搜尋        （vector_search，Milvus）
            ├─ 入模前  ：檢索結束 → agent_llm 開始（組 prompt、建 agent、綁工具）
            ├─ Prefill ：agent_llm 開始 → 首 token（含到供應商的網路來回）
            ├─ 生成    ：首 token → agent_llm 結束
            └─ 收尾    ：最終回覆組裝 + 對話持久化

只有 Prefill 與 生成 兩段跟模型選擇有關；其餘幾段對所有模型都一樣，
是「換模型救不了」的部分——這正是做性價比決策時最容易看錯的地方。

用法：
  TENANT_ADMIN_PASSWORD=... python3 scripts/local_model_eval/trace_breakdown.py \\
      --base-url https://agentic-rag-969010424468.asia-east1.run.app \\
      --account eval-admin@example.com [--limit 200] [--out breakdown.md]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path


def call(base: str, token: str, path: str):
    req = urllib.request.Request(base.rstrip("/") + path, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GET {path} -> {e.code}: {e.read()[:200]!r}") from None


def login(base: str, account: str, pw: str) -> str:
    req = urllib.request.Request(
        base.rstrip("/") + "/api/v1/auth/login",
        data=json.dumps({"account": account, "password": pw}).encode(),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["access_token"]


def _node(nodes: dict, *names):
    for n in names:
        if n in nodes:
            return nodes[n]
    return None


def segments(trace: dict) -> dict | None:
    """單一 trace → 各分段毫秒數；缺關鍵節點就跳過（不猜）。"""
    nodes: dict = {}
    for n in trace.get("nodes") or []:
        nodes.setdefault(n.get("node_type") or "", n)

    req = _node(nodes, "request")
    llm = _node(nodes, "agent_llm")
    ft = _node(nodes, "first_token")
    if not req or not llm:
        return None

    retr = _node(nodes, "direct_retrieval", "tool_result")
    emb = _node(nodes, "embed_query")
    vec = _node(nodes, "vector_search")
    guard_end = max(
        (x.get("end_ms") or 0)
        for x in (_node(nodes, "guard_stages"), _node(nodes, "bot_load"),
                  _node(nodes, "conversation_load"))
        if x
    ) if any(_node(nodes, k) for k in ("guard_stages", "bot_load", "conversation_load")) else 0.0

    llm_start = llm.get("start_ms") or 0.0
    llm_end = llm.get("end_ms") or 0.0
    req_end = req.get("end_ms") or llm_end
    retr_start = (retr.get("start_ms") if retr else guard_end) or guard_end
    retr_end = (retr.get("end_ms") if retr else llm_start) or llm_start
    ft_at = (ft.get("start_ms") if ft else None)

    out = {
        "前置": max(0.0, retr_start),
        "Embedding": (emb.get("duration_ms") or 0.0) if emb else 0.0,
        "向量搜尋": (vec.get("duration_ms") or 0.0) if vec else 0.0,
        "檢索小計": max(0.0, retr_end - retr_start),
        "入模前": max(0.0, llm_start - retr_end),
        "收尾": max(0.0, req_end - llm_end),
        "總計": req.get("duration_ms") or trace.get("total_ms") or req_end,
    }
    if ft_at is not None:
        out["Prefill"] = max(0.0, ft_at - llm_start)
        out["生成"] = max(0.0, llm_end - ft_at)
    else:
        out["Prefill"] = None
        out["生成"] = None
    return out


ORDER = ["前置", "Embedding", "向量搜尋", "檢索小計", "入模前", "Prefill", "生成", "收尾", "總計"]
MODEL_DEPENDENT = {"Prefill", "生成"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--account", default="eval-admin@example.com")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    pw = os.environ.get("TENANT_ADMIN_PASSWORD")
    if not pw:
        print("請以環境變數 TENANT_ADMIN_PASSWORD 提供密碼")
        return 2

    token = login(args.base_url, args.account, pw)
    data = call(args.base_url, token, f"/api/v1/observability/agent-traces?limit={args.limit}")
    traces = data if isinstance(data, list) else data.get("items", [])

    by_model: dict[str, list[dict]] = defaultdict(list)
    skipped = 0
    for t in traces:
        seg = segments(t)
        if seg is None:
            skipped += 1
            continue
        by_model[t.get("llm_model") or "?"].append(seg)

    lines: list[str] = []
    lines.append(f"# 分段耗時（中位數 ms，取自 agent trace 伺服器端計時）\n")
    lines.append(f"樣本：{len(traces)} 筆 trace，可用 {sum(len(v) for v in by_model.values())} 筆"
                 f"（缺關鍵節點跳過 {skipped} 筆）\n")
    lines.append("| 模型 | n | " + " | ".join(ORDER) + " |")
    lines.append("|---|---|" + "---|" * len(ORDER))
    for model, segs in sorted(by_model.items(), key=lambda kv: -len(kv[1])):
        row = [model, str(len(segs))]
        for k in ORDER:
            vals = [s[k] for s in segs if s.get(k) is not None]
            row.append(f"{statistics.median(vals):.0f}" if vals else "-")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("\n## 換模型救得到 vs 救不到\n")
    lines.append("| 模型 | n | 模型相關（Prefill+生成） | 管線固定（其餘） | 模型佔比 |")
    lines.append("|---|---|---|---|---|")
    for model, segs in sorted(by_model.items(), key=lambda kv: -len(kv[1])):
        dep = [sum(s[k] or 0 for k in MODEL_DEPENDENT) for s in segs if s.get("Prefill") is not None]
        tot = [s["總計"] for s in segs if s.get("Prefill") is not None]
        if not dep:
            continue
        md, mt = statistics.median(dep), statistics.median(tot)
        lines.append(f"| {model} | {len(dep)} | {md:.0f} | {mt - md:.0f} | {md / mt * 100:.0f}% |")

    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"\n已寫入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
