#!/usr/bin/env python3
"""工具呼叫題組跑題器 —— 量「有沒有選對工具」與「叫了幾次」。

評分訊號直接來自 /api/v1/agent/chat 回應的 tool_calls[]（含 tool_name 與 reasoning），
不必挖 trace。每輪記錄：

  expected     題目期望的工具集合（空集合＝不該叫工具）
  actual       實際呼叫的工具（依序，含重複）
  expected_n   期望次數（=期望集合大小）
  actual_n     實際次數
  correct      集合完全相符
  missing      該叫沒叫
  extra        多叫的
  forbidden    叫到明確禁止的（例如答得出來卻直接轉真人）

為什麼「多叫」也要扣分：過度呼叫是最常見的失敗模式，每多一次就是一次額外的
檢索或轉接動作，成本與延遲都上去，使用者還會看到莫名其妙的轉接按鈕。

用法：
  TENANT_ADMIN_PASSWORD=... python3 scripts/local_model_eval/run_tools.py \\
      --base-url https://agentic-rag-969010424468.asia-east1.run.app \\
      --account eval-admin@example.com [--bot-prefix "工具 "] [--repeat 1]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
_RETRY_AFTER = re.compile(r"(\d+)\s*seconds")


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.token = ""
        self._creds: tuple[str, str] | None = None

    def call(self, method: str, path: str, body: dict | None = None, timeout: int = 300):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode() if body else None, method=method,
        )
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {"detail": raw.decode(errors="ignore")[:300]}

    def login(self, account: str, pw: str) -> None:
        st, r = self.call("POST", "/api/v1/auth/login", {"account": account, "password": pw})
        if st != 200:
            raise SystemExit(f"login failed {st}: {r}")
        self.token = r["access_token"]
        self._creds = (account, pw)

    def relogin(self) -> bool:
        if not self._creds:
            return False
        st, r = self.call("POST", "/api/v1/auth/login",
                          {"account": self._creds[0], "password": self._creds[1]})
        if st != 200:
            return False
        self.token = r["access_token"]
        print("      access token 過期，已重新登入", flush=True)
        return True


def ask(api: Api, bot_id: str, message: str, conversation_id: str | None, *, max_retry: int = 6):
    body = {"message": message, "bot_id": bot_id,
            **({"conversation_id": conversation_id} if conversation_id else {})}
    t0 = time.perf_counter()
    st, r = 0, None
    for attempt in range(max_retry):
        st, r = api.call("POST", "/api/v1/agent/chat", body)
        if st == 401 and api.relogin():
            st, r = api.call("POST", "/api/v1/agent/chat", body)
        if st != 429:
            break
        detail = str((r or {}).get("detail", ""))
        m = _RETRY_AFTER.search(detail)
        wait = min(int(m.group(1)) + 2 if m else 15 * (attempt + 1), 90)
        print(f"      429 速率限制，等 {wait}s（{attempt + 1}/{max_retry}）", flush=True)
        time.sleep(wait)
    ms = round((time.perf_counter() - t0) * 1000)
    if st != 200:
        return {"ok": False, "status": st, "answer": json.dumps(r, ensure_ascii=False)[:400],
                "latency_ms": ms, "tool_calls": [], "conversation_id": conversation_id,
                "input_tokens": 0, "output_tokens": 0}
    u = r.get("usage") or {}
    return {
        "ok": True, "status": st, "answer": r.get("answer", ""), "latency_ms": ms,
        "conversation_id": r.get("conversation_id") or conversation_id,
        "input_tokens": u.get("input_tokens") or 0,
        "output_tokens": u.get("output_tokens") or 0,
        "tool_calls": [
            {"tool_name": t.get("tool_name", ""), "reasoning": (t.get("reasoning") or "")[:300]}
            for t in (r.get("tool_calls") or [])
        ],
    }


# ReAct 在「沒有使用任何工具」時會回一筆 tool_name="direct" 的假紀錄
# （react_agent_service.py:1396），那不是真的工具呼叫，判分要當成空集合，
# 否則所有「不該叫工具」的題目會全數誤判為多叫一次。
_NOT_A_TOOL = {"direct", ""}


def judge(expected: list[str], forbidden: list[str], actual_names: list[str]) -> dict:
    actual_names = [n for n in actual_names if n not in _NOT_A_TOOL]
    exp, act = set(expected), set(actual_names)
    forb = set(forbidden) & act
    return {
        "expected_n": len(exp), "actual_n": len(actual_names),
        "unique_actual_n": len(act),
        "correct": act == exp and not forb,
        "missing": sorted(exp - act), "extra": sorted(act - exp),
        "forbidden_hit": sorted(forb),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--account", default="eval-admin@example.com")
    ap.add_argument("--cases", default=str(HERE / "cases" / "tools20_2026-09-08.json"))
    ap.add_argument("--bot-prefix", default="工具 ")
    ap.add_argument("--only", default="")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()

    pw = os.environ.get("TENANT_ADMIN_PASSWORD")
    if not pw:
        print("請以環境變數 TENANT_ADMIN_PASSWORD 提供密碼")
        return 2

    spec = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    dialogues = [d for d in spec["dialogues"] if not only or d["id"] in only]

    api = Api(args.base_url)
    api.login(args.account, pw)
    st, bots = api.call("GET", "/api/v1/bots?page=1&page_size=200")
    items = bots if isinstance(bots, list) else bots.get("items", [])
    targets = [b for b in items if b["name"].startswith(args.bot_prefix)]
    if not targets:
        print(f"找不到「{args.bot_prefix}」開頭的 bot，先跑 scripts/setup_tool_eval_bots.py")
        return 1

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out = RESULTS / f"tools_{stamp}.jsonl"
    rows: list[dict] = []

    with out.open("w", encoding="utf-8") as fh:
        for rep in range(1, args.repeat + 1):
            for bot in targets:
                name, bid = bot["name"], bot["id"]
                print(f"==> [第 {rep} 次] {name}", flush=True)
                for d in dialogues:
                    conv = None
                    for t in d["turns"]:
                        # independent_turns 的段落每輪都開新對話，避免上下文互相污染
                        if d.get("independent_turns"):
                            conv = None
                        r = ask(api, bid, t["user"], conv)
                        conv = r.get("conversation_id") or conv
                        names = [c["tool_name"] for c in r["tool_calls"]]
                        verdict = judge(t.get("expect_tools", []), t.get("forbid_tools", []), names)
                        rec = {
                            "run": rep, "bot": name, "dialogue": d["id"], "tier": d["tier"],
                            "turn": t["n"], "user": t["user"], "gold": t.get("gold", ""),
                            "expect_tools": t.get("expect_tools", []),
                            "forbid_tools": t.get("forbid_tools", []),
                            "actual_tools": names,
                            "tool_reasonings": [c["reasoning"] for c in r["tool_calls"]],
                            "answer": r["answer"], "ok": r["ok"],
                            "latency_ms": r["latency_ms"],
                            "input_tokens": r["input_tokens"],
                            "output_tokens": r["output_tokens"],
                            **verdict,
                        }
                        rows.append(rec)
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fh.flush()
                        mark = "✓" if verdict["correct"] else "✗"
                        print(f"   {d['id']}-{t['n']} {mark} 期望{verdict['expected_n']} "
                              f"實際{verdict['actual_n']} {names} {r['latency_ms']}ms", flush=True)
                        time.sleep(args.sleep)

    ok_rows = [r for r in rows if r["ok"]]
    by = defaultdict(list)
    for r in ok_rows:
        by[r["bot"]].append(r)

    print("\n## 工具呼叫總表\n")
    print("| bot | 輪數 | 選對率 | 平均呼叫次數 | 期望平均 | 該叫沒叫 | 多叫 | 叫到禁止的 |")
    print("|---|---|---|---|---|---|---|---|")
    for b, rs in sorted(by.items(), key=lambda kv: -sum(x["correct"] for x in kv[1]) / max(1, len(kv[1]))):
        n = len(rs)
        print(f"| {b} | {n} | {sum(r['correct'] for r in rs) / n * 100:.0f}% | "
              f"{statistics.mean(r['actual_n'] for r in rs):.2f} | "
              f"{statistics.mean(r['expected_n'] for r in rs):.2f} | "
              f"{sum(1 for r in rs if r['missing'])} | {sum(1 for r in rs if r['extra'])} | "
              f"{sum(1 for r in rs if r['forbidden_hit'])} |")

    print("\n## 依情境類型的選對率\n")
    tiers = sorted({r["tier"] for r in ok_rows})
    print("| bot | " + " | ".join(tiers) + " |")
    print("|---" * (len(tiers) + 1) + "|")
    for b, rs in sorted(by.items()):
        cells = []
        for t in tiers:
            sub = [r for r in rs if r["tier"] == t]
            cells.append(f"{sum(x['correct'] for x in sub) / len(sub) * 100:.0f}%" if sub else "-")
        print(f"| {b} | " + " | ".join(cells) + " |")

    print("\n## 最常見的錯誤\n")
    errs = Counter()
    for r in ok_rows:
        if r["correct"]:
            continue
        errs[(r["dialogue"], r["turn"], tuple(r["missing"]), tuple(r["extra"]))] += 1
    for (d, t, miss, extra), c in errs.most_common(12):
        print(f"- `{d}-{t}` ×{c}　該叫沒叫={list(miss) or '-'}　多叫={list(extra) or '-'}")

    print(f"\n輸出：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
