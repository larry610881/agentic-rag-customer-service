#!/usr/bin/env python3
"""結構化輸出（output_format=json）題組跑題器。

量四件事，分開記，因為它們的失敗成因完全不同：

1. **可解析**：回應能不能直接 ``json.loads``。若要先剝掉 markdown code fence 才能解析，
   單獨記為 ``fenced``——這正是廠商 LumineOne 的已知病徵（間歇把 JSON 包進 ```json ```），
   前端解析會直接爆掉。分開記才看得出「模型會不會犯同樣的病」。
2. **合 schema**：三個欄位齊全、型別正確、status/category 落在列舉值內、無多餘欄位。
3. **status 正確**：命中題要 answered、範圍外題要 out_of_scope。
4. **內容**：out_of_scope 時 answer 必須為空字串（有值＝在該拒答時編了東西）。

回應優先讀 ``structured_content``（平台已解析好的物件）；沒有才退回自己解析 ``answer``
字串——後者才是真正在考模型的格式紀律，所以兩個來源分開統計。

用法：
  TENANT_ADMIN_PASSWORD=... python3 scripts/local_model_eval/run_json.py \\
      --base-url https://agentic-rag-969010424468.asia-east1.run.app \\
      [--bot-prefix "JSON "] [--repeat 1] [--exclude gemini]
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
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


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
        st, r = self.call("POST", "/api/v1/auth/login",
                          {"account": account, "password": pw})
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


def parse_output(answer: str) -> tuple[dict | None, str]:
    """回傳 (物件, 解析方式)。方式：direct / fenced / unparseable。"""
    text = (answer or "").strip()
    if not text:
        return None, "unparseable"
    try:
        obj = json.loads(text)
        return (obj, "direct") if isinstance(obj, dict) else (None, "unparseable")
    except Exception:
        pass
    m = _FENCE.match(text)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return obj, "fenced"
        except Exception:
            pass
    return None, "unparseable"


def check_schema(obj: dict, schema: dict) -> list[str]:
    """回傳違規清單；空 = 合 schema。"""
    problems: list[str] = []
    props = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in obj:
            problems.append(f"缺欄位 {key}")
    for key, val in obj.items():
        spec = props.get(key)
        if spec is None:
            problems.append(f"多餘欄位 {key}")
            continue
        if spec.get("type") == "string" and not isinstance(val, str):
            problems.append(f"{key} 型別非 string")
            continue
        enum = spec.get("enum")
        if enum and val not in enum:
            problems.append(f"{key}={val!r} 不在列舉值內")
    return problems


def ask(api: Api, bot_id: str, message: str, *, max_retry: int = 6):
    body = {"message": message, "bot_id": bot_id}
    t0 = time.perf_counter()
    st, r = 0, None
    for attempt in range(max_retry):
        st, r = api.call("POST", "/api/v1/agent/chat", body)
        if st == 401 and api.relogin():
            st, r = api.call("POST", "/api/v1/agent/chat", body)
        if st != 429:
            break
        m = _RETRY_AFTER.search(str((r or {}).get("detail", "")))
        wait = min(int(m.group(1)) + 2 if m else 15 * (attempt + 1), 90)
        print(f"      429 速率限制，等 {wait}s（{attempt + 1}/{max_retry}）", flush=True)
        time.sleep(wait)
    ms = round((time.perf_counter() - t0) * 1000)
    if st != 200:
        return {"ok": False, "status": st, "answer": json.dumps(r, ensure_ascii=False)[:400],
                "structured": None, "latency_ms": ms}
    return {"ok": True, "status": st, "answer": r.get("answer", ""),
            "structured": r.get("structured_content"), "latency_ms": ms}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--account", default="eval-admin@example.com")
    ap.add_argument("--cases", default=str(HERE / "cases" / "json12_2026-09-08.json"))
    ap.add_argument("--bot-prefix", default="JSON ")
    ap.add_argument("--exclude", default="")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()

    pw = os.environ.get("TENANT_ADMIN_PASSWORD")
    if not pw:
        print("請以環境變數 TENANT_ADMIN_PASSWORD 提供密碼")
        return 2

    spec = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    schema = spec["schema"]

    api = Api(args.base_url)
    api.login(args.account, pw)
    _st, bots = api.call("GET", "/api/v1/bots?page=1&page_size=200")
    items = bots if isinstance(bots, list) else bots.get("items", [])
    skip = [x.strip() for x in args.exclude.split(",") if x.strip()]
    targets = [b for b in items if b["name"].startswith(args.bot_prefix)
               and not any(x in b["name"] for x in skip)]
    if not targets:
        print(f"找不到「{args.bot_prefix}」開頭的 bot，先跑 scripts/setup_json_eval_bots.py")
        return 1

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out = RESULTS / f"json_{stamp}.jsonl"
    rows: list[dict] = []

    with out.open("w", encoding="utf-8") as fh:
        for rep in range(1, args.repeat + 1):
            for bot in targets:
                print(f"==> [第 {rep} 次] {bot['name']}", flush=True)
                for d in spec["dialogues"]:
                    for t in d["turns"]:
                        r = ask(api, bot["id"], t["user"])
                        obj, how = parse_output(r["answer"])
                        # 平台已解析好的物件（native_schema 路徑）另記，
                        # 但格式紀律要看模型自己吐的字串
                        if obj is None and isinstance(r.get("structured"), dict):
                            obj, how = r["structured"], "platform_parsed"
                        problems = check_schema(obj, schema) if obj else ["無法解析"]
                        status = (obj or {}).get("status")
                        answer_field = (obj or {}).get("answer", "")
                        rec = {
                            "run": rep, "bot": bot["name"], "dialogue": d["id"],
                            "tier": d["tier"], "turn": t["n"], "user": t["user"],
                            "gold": t.get("gold", ""),
                            "expect_status": t.get("expect_status"),
                            "raw": r["answer"][:1200], "parsed_how": how,
                            "parsable": obj is not None,
                            "schema_ok": bool(obj) and not problems,
                            "schema_problems": problems,
                            "status": status,
                            "status_ok": status == t.get("expect_status"),
                            "answer_field": answer_field[:500],
                            "empty_answer_ok": (
                                (answer_field.strip() == "")
                                if t.get("expect_status") == "out_of_scope" else None
                            ),
                            "ok": r["ok"], "latency_ms": r["latency_ms"],
                        }
                        rows.append(rec)
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fh.flush()
                        mark = "✓" if rec["schema_ok"] and rec["status_ok"] else "✗"
                        print(f"   {d['id']}-{t['n']} {mark} {how:<15} "
                              f"status={status} {r['latency_ms']}ms", flush=True)
                        time.sleep(args.sleep)

    ok_rows = [r for r in rows if r["ok"]]
    by = defaultdict(list)
    for r in ok_rows:
        by[r["bot"]].append(r)

    print("\n## 結構化輸出總表\n")
    print("| bot | 輪數 | 可解析 | 需剝 fence | 合 schema | status 正確 | 該空未空 |")
    print("|---|---|---|---|---|---|---|")
    for b, rs in sorted(by.items(), key=lambda kv: -sum(x["schema_ok"] for x in kv[1])):
        n = len(rs)
        fenced = sum(1 for r in rs if r["parsed_how"] == "fenced")
        bad_empty = sum(1 for r in rs if r["empty_answer_ok"] is False)
        print(f"| {b} | {n} | {sum(r['parsable'] for r in rs) / n * 100:.0f}% | {fenced} | "
              f"{sum(r['schema_ok'] for r in rs) / n * 100:.0f}% | "
              f"{sum(r['status_ok'] for r in rs) / n * 100:.0f}% | {bad_empty} |")

    print("\n## 依情境類型的 schema 通過率\n")
    tiers = sorted({r["tier"] for r in ok_rows})
    print("| bot | " + " | ".join(tiers) + " |")
    print("|---" * (len(tiers) + 1) + "|")
    for b, rs in sorted(by.items()):
        cells = []
        for t in tiers:
            sub = [r for r in rs if r["tier"] == t]
            cells.append(f"{sum(x['schema_ok'] for x in sub) / len(sub) * 100:.0f}%"
                         if sub else "-")
        print(f"| {b} | " + " | ".join(cells) + " |")

    probs = Counter()
    for r in ok_rows:
        for p in r["schema_problems"]:
            probs[(r["bot"], p)] += 1
    if probs:
        print("\n## schema 違規排行\n")
        for (b, p), c in probs.most_common(15):
            print(f"- {b}　{p}　×{c}")

    lat = [r["latency_ms"] for r in ok_rows]
    if lat:
        print(f"\n延遲中位數 {statistics.median(lat):.0f} ms")
    print(f"\n輸出：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
