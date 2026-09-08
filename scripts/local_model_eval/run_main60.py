#!/usr/bin/env python3
"""60 輪主題組跑題器（多輪對話、多模型、可重跑多次）。

對評測租戶裡名稱以「評測 」開頭的每個 bot，依 cases/main60_*.json 逐段對話送出，
同一段對話共用一個 conversation_id，輸出每輪一列的 JSONL。

跟 run_quick20.py 的差別：題組從 JSON 檔讀（不寫死）、支援 --repeat 多次重跑、
每輪獨立記錄（不把同段對話併成一列），方便之後做盲評與跨輪分析。

用法：
  TENANT_ADMIN_PASSWORD=... python3 scripts/local_model_eval/run_main60.py \\
      --base-url https://agentic-rag-969010424468.asia-east1.run.app \\
      --account eval-admin@example.com \\
      --cases scripts/local_model_eval/cases/main60_2026-09-08.json \\
      [--bots "評測 A,評測 B"] [--only E1,H3] [--repeat 1]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
_RETRY_AFTER = re.compile(r"(\d+)\s*seconds")


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.token = ""

    def call(self, method: str, path: str, body: dict | None = None, timeout: int = 300):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode() if body else None,
            method=method,
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


def ask(api: Api, bot_id: str, message: str, conversation_id: str | None, *, max_retry: int = 6):
    """送一輪；遇到平台速率限制（429）依訊息指定秒數等待後重試。"""
    body = {
        "message": message,
        "bot_id": bot_id,
        **({"conversation_id": conversation_id} if conversation_id else {}),
    }
    t0 = time.perf_counter()
    st, r = 0, None
    for attempt in range(max_retry):
        st, r = api.call("POST", "/api/v1/agent/chat", body)
        if st != 429:
            break
        detail = str((r or {}).get("detail", ""))
        m = _RETRY_AFTER.search(detail)
        wait = min(int(m.group(1)) + 2 if m else 15 * (attempt + 1), 90)
        print(f"      429 速率限制，等 {wait}s 後重試（{attempt + 1}/{max_retry}）", flush=True)
        time.sleep(wait)
    ms = round((time.perf_counter() - t0) * 1000)
    if st != 200:
        return {
            "ok": False, "status": st, "answer": json.dumps(r, ensure_ascii=False)[:600],
            "latency_ms": ms, "conversation_id": conversation_id,
            "input_tokens": 0, "output_tokens": 0, "sources": [],
        }
    u = r.get("usage") or {}
    return {
        "ok": True, "status": st, "answer": r.get("answer", ""), "latency_ms": ms,
        "conversation_id": r.get("conversation_id") or conversation_id,
        "input_tokens": u.get("input_tokens") or 0,
        "output_tokens": u.get("output_tokens") or 0,
        "model": u.get("model", ""),
        "sources": [s.get("document_name") for s in (r.get("sources") or [])][:5],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--account", default="eval-admin@example.com")
    ap.add_argument("--cases", default=str(HERE / "cases" / "main60_2026-09-08.json"))
    ap.add_argument("--bots", default="", help="逗號分隔 bot 名稱；空 = 所有「評測 」開頭的 bot")
    ap.add_argument("--only", default="", help="逗號分隔對話 id，如 E1,H3")
    ap.add_argument("--repeat", type=int, default=1, help="整份題組重跑幾次（看穩定度）")
    ap.add_argument("--sleep", type=float, default=1.0, help="每輪之間的間隔秒數")
    args = ap.parse_args()

    pw = os.environ.get("TENANT_ADMIN_PASSWORD")
    if not pw:
        print("請以環境變數 TENANT_ADMIN_PASSWORD 提供密碼")
        return 2

    spec = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    dialogues = [d for d in spec["dialogues"] if not only or d["id"] in only]
    total_turns = sum(len(d["turns"]) for d in dialogues)

    api = Api(args.base_url)
    api.login(args.account, pw)
    st, bots = api.call("GET", "/api/v1/bots?page=1&page_size=200")
    items = bots if isinstance(bots, list) else bots.get("items", [])
    wanted = [b.strip() for b in args.bots.split(",") if b.strip()]
    targets = (
        [b for b in items if b["name"] in wanted] if wanted
        else [b for b in items if b["name"].startswith("評測 ")]
    )
    if not targets:
        print("找不到評測 bot")
        return 1

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out = RESULTS / f"main60_{stamp}.jsonl"
    print(f"題組 {spec['version']}：{len(dialogues)} 段 / {total_turns} 輪 × "
          f"{len(targets)} bot × {args.repeat} 次 = {total_turns * len(targets) * args.repeat} 次呼叫")

    with out.open("w", encoding="utf-8") as fh:
        for rep in range(1, args.repeat + 1):
            for bot in targets:
                name, bid = bot["name"], bot["id"]
                print(f"==> [第 {rep} 次] {name}", flush=True)
                for d in dialogues:
                    conv = None
                    for t in d["turns"]:
                        r = ask(api, bid, t["user"], conv)
                        conv = r.get("conversation_id") or conv
                        rec = {
                            "run": rep, "bot": name, "bot_id": bid,
                            "dialogue": d["id"], "tier": d["tier"], "title": d["title"],
                            "turn": t["n"], "user": t["user"], "gold": t["gold"],
                            "answer": r["answer"], "ok": r["ok"],
                            "latency_ms": r["latency_ms"],
                            "input_tokens": r["input_tokens"],
                            "output_tokens": r["output_tokens"],
                            "model": r.get("model", ""), "sources": r.get("sources", []),
                            "conversation_id": conv,
                        }
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fh.flush()
                        flag = "OK" if r["ok"] else f"ERR{r['status']}"
                        print(f"   {d['id']}-{t['n']} {r['latency_ms']}ms "
                              f"in={r['input_tokens']} out={r['output_tokens']} {flag}", flush=True)
                        time.sleep(args.sleep)
    print(f"\n輸出：{out}")
    print("下一步：python3 scripts/local_model_eval/make_blind_packet.py --results "
          f"{out} --out-dir ~/qa-scoring")
    return 0


if __name__ == "__main__":
    sys.exit(main())
