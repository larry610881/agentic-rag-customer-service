#!/usr/bin/env python3
"""把多個結果檔彙整成一份完整評測報告（六張表）。

刻意接受**多個檔案**而不是單一檔：一天下來資料是分批產生的（不同臂在不同時間跑、
中途修了 bug 要重跑），硬要合成單一檔反而容易把修復前後的資料混在一起。這支腳本
以「檔案清單」為輸入，並在報告開頭列出每個檔的來源與臂別，讓讀的人自己看得到組成。

六張表：
1. 效能（首 token / 總時間 / 字元秒 / 估算 token 秒）
2. 穩定度（同題多次執行的事實覆蓋是否翻動）
3. 金標準數字覆蓋率（**機械篩選，不是準確率**）
4. 依輪次的覆蓋率（抓多輪衰減，Issue #87 就是這樣抓到的）
5. 工具呼叫（選對率 / 呼叫次數 / 三類錯誤）
6. 結構化輸出（可解析 / 合 schema / status 正確）

用法：
  cd apps/backend && uv run python ../../scripts/local_model_eval/build_report.py \\
      --main ../../scripts/local_model_eval/results/main60_A.jsonl \\
             ../../scripts/local_model_eval/results/main60_B.jsonl \\
      --tools ../../scripts/local_model_eval/results/tools_X.jsonl \\
      --json  ../../scripts/local_model_eval/results/json_Y.jsonl \\
      --out ../../docs/model-eval-report-2026-09-08.md
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

NUM = re.compile(r"\d[\d,\./%-]*")


def load(paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for p in paths:
        f = Path(p)
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                r["_src"] = f.name
                rows.append(r)
    return rows


def arm(name: str) -> str:
    for prefix in ("評測 ", "工具 ", "JSON "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def gold_facts(g: str) -> set[str]:
    return {
        m.group(0).rstrip(".、，,")
        for m in NUM.finditer(g or "")
        if len(m.group(0).rstrip(".、，,")) >= 2
    }


def covered(gold: str, ans: str) -> frozenset[str]:
    a = (ans or "").replace(",", "").replace("，", "")
    return frozenset(k for k in gold_facts(gold) if k.replace(",", "") in a)


def encoder():
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def table(out: list[str], header: list[str], rows: list[list[str]]) -> None:
    out.append("| " + " | ".join(header) + " |")
    out.append("|" + "---|" * len(header))
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    out.append("")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", nargs="*", default=[])
    ap.add_argument("--tools", nargs="*", default=[])
    ap.add_argument("--json", nargs="*", default=[], dest="json_files")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    enc = encoder()
    out: list[str] = ["# 模型評測報告（2026-09-08）\n"]

    # --- 資料來源 ---
    out.append("## 0. 資料來源\n")
    src_rows = []
    for label, paths in (("問答 60 輪", args.main), ("工具 20 輪", args.tools),
                         ("結構化 12 輪", args.json_files)):
        for p in paths:
            rows = load([p])
            arms = sorted({arm(r["bot"]) for r in rows})
            runs = sorted({r.get("run", 1) for r in rows})
            src_rows.append([label, Path(p).name, str(len(rows)),
                             f"{len(runs)} 輪", "、".join(arms)])
    table(out, ["題組", "檔案", "列數", "重跑", "受測模型"], src_rows)

    main_rows = [r for r in load(args.main) if r.get("ok")]
    tool_rows = [r for r in load(args.tools) if r.get("ok")]
    json_rows = [r for r in load(args.json_files) if r.get("ok")]

    # --- 1. 效能 ---
    if main_rows:
        out.append("## 1. 效能（中位數）\n")
        if enc:
            out.append("> token 估算用 tiktoken cl100k，所有模型同一把尺——"
                       "**只能跨模型比快慢，不可拿來算錢**。\n")
        perf = defaultdict(list)
        for r in main_rows:
            if not r.get("ttft_ms"):
                continue
            gen = max(1, r["latency_ms"] - r["ttft_ms"])
            txt = r.get("answer") or ""
            perf[arm(r["bot"])].append((
                r["ttft_ms"], r["latency_ms"], len(txt) / (gen / 1000),
                (len(enc.encode(txt)) / (gen / 1000)) if enc else None,
            ))
        rows = []
        for a, v in sorted(perf.items(), key=lambda kv: statistics.median(x[1] for x in kv[1])):
            med = lambda i: statistics.median(x[i] for x in v)  # noqa: E731
            cells = [a, str(len(v)), f"{med(0):.0f}", f"{med(1):.0f}", f"{med(2):.0f}"]
            if enc:
                cells.append(f"{med(3):.0f}")
            rows.append(cells)
        head = ["模型", "n", "首 token ms", "總時間 ms", "字元/秒"]
        if enc:
            head.append("估算 token/秒")
        table(out, head, rows)

    # --- 2. 穩定度 ---
    if main_rows:
        out.append("## 2. 穩定度（同題多次執行，金標準事實覆蓋是否一致）\n")
        cells_: dict[tuple, list] = defaultdict(list)
        for r in main_rows:
            cells_[(arm(r["bot"]), r["dialogue"], r["turn"])].append(r)
        stab = defaultdict(lambda: [0, 0])
        for (a, _d, _t), rs in cells_.items():
            if len(rs) < 2 or not gold_facts(rs[0]["gold"]):
                continue
            stab[a][0] += 1
            if len({covered(x["gold"], x["answer"]) for x in rs}) > 1:
                stab[a][1] += 1
        table(out, ["模型", "可比題數", "會翻動", "翻動率"],
              [[a, str(n), str(f), f"{f / n * 100:.0f}%"]
               for a, (n, f) in sorted(stab.items(), key=lambda kv: kv[1][1] / max(1, kv[1][0]))])

    # --- 3+4. 覆蓋率 ---
    if main_rows:
        out.append("## 3. 金標準數字覆蓋率\n")
        out.append("> ⚠️ **這不是準確率**。它只檢查金標準裡的數字有沒有出現在回答字串中，"
                   "會誤判兩個方向：金標準寫「7/1」而模型寫「7月1日」算漏（假錯）；"
                   "數字出現在錯的地方也算命中（假對）。它的用途是**抓大異常**"
                   "（例如 Issue #87 讓 Gemini 掉到 41.5%），不足以分辨 5 個百分點的差距。"
                   "真正的準確率要看盲評。\n")
        cov = defaultdict(lambda: [0, 0])
        by_turn = defaultdict(lambda: [0, 0])
        for r in main_rows:
            a = arm(r["bot"])
            for k in gold_facts(r["gold"]):
                hit = k.replace(",", "") in (r["answer"] or "").replace(",", "").replace("，", "")
                cov[a][1] += 1
                by_turn[(a, r["turn"])][1] += 1
                if hit:
                    cov[a][0] += 1
                    by_turn[(a, r["turn"])][0] += 1
        table(out, ["模型", "命中/應命中", "覆蓋率"],
              [[a, f"{h}/{n}", f"{h / n * 100:.1f}%"]
               for a, (h, n) in sorted(cov.items(), key=lambda kv: -kv[1][0] / kv[1][1])])

        out.append("## 4. 依輪次的覆蓋率（抓多輪衰減）\n")
        out.append("> Issue #87 就是靠這張表抓到的：Gemini 修復前為 89/36/18/10/17%，"
                   "其餘四臂全程 77–100%。單看總分看不出來。\n")
        turns = sorted({t for _a, t in by_turn})
        rows = []
        for a in sorted(cov):
            cells = [a]
            for t in turns:
                h, n = by_turn.get((a, t), [0, 0])
                cells.append(f"{h / n * 100:.0f}%" if n else "-")
            rows.append(cells)
        table(out, ["模型"] + [f"第{t}輪" for t in turns], rows)

    # --- 5. 工具 ---
    if tool_rows:
        out.append("## 5. 工具呼叫\n")
        by = defaultdict(list)
        for r in tool_rows:
            by[arm(r["bot"])].append(r)
        rows = []
        for a, rs in sorted(by.items(), key=lambda kv: -sum(x["correct"] for x in kv[1]) / len(kv[1])):
            n = len(rs)
            rows.append([
                a, str(n), f"{sum(r['correct'] for r in rs) / n * 100:.0f}%",
                f"{statistics.mean(r['actual_n'] for r in rs):.2f}",
                f"{statistics.mean(r['expected_n'] for r in rs):.2f}",
                str(sum(1 for r in rs if r["missing"])),
                str(sum(1 for r in rs if r["extra"])),
                str(sum(1 for r in rs if r["forbidden_hit"])),
            ])
        table(out, ["模型", "輪數", "選對率", "平均呼叫", "期望平均",
                    "該叫沒叫", "多叫", "叫到禁止的"], rows)

        tiers = sorted({r["tier"] for r in tool_rows})
        out.append("### 依情境類型的選對率\n")
        rows = []
        for a, rs in sorted(by.items()):
            cells = [a]
            for t in tiers:
                sub = [r for r in rs if r["tier"] == t]
                cells.append(f"{sum(x['correct'] for x in sub) / len(sub) * 100:.0f}%" if sub else "-")
            rows.append(cells)
        table(out, ["模型"] + tiers, rows)

    # --- 6. 結構化輸出 ---
    if json_rows:
        out.append("## 6. 結構化輸出（output_format=json）\n")
        by = defaultdict(list)
        for r in json_rows:
            by[arm(r["bot"])].append(r)
        rows = []
        for a, rs in sorted(by.items(), key=lambda kv: -sum(x["schema_ok"] for x in kv[1]) / len(kv[1])):
            n = len(rs)
            rows.append([
                a, str(n),
                f"{sum(r['parsable'] for r in rs) / n * 100:.0f}%",
                str(sum(1 for r in rs if r["parsed_how"] == "fenced")),
                f"{sum(r['schema_ok'] for r in rs) / n * 100:.0f}%",
                f"{sum(r['status_ok'] for r in rs) / n * 100:.0f}%",
                str(sum(1 for r in rs if r["empty_answer_ok"] is False)),
            ])
        table(out, ["模型", "輪數", "可解析", "需剝 fence", "合 schema",
                    "status 正確", "該空未空"], rows)

        # 跨臂完全一致 = 平台在說話，不是模型在說話。2026-09-08 這張表五臂
        # 都是 92/92/83%，失分全部來自防護攔截回純文字的那一題（#85 的漏網
        # 路徑），模型根本沒被呼叫。這種表沒有鑑別度，必須當場講出來。
        sig = {
            a: (
                round(sum(r["parsable"] for r in rs) / len(rs), 4),
                round(sum(r["schema_ok"] for r in rs) / len(rs), 4),
                round(sum(r["status_ok"] for r in rs) / len(rs), 4),
            )
            for a, rs in by.items()
        }
        if len(by) > 1 and len(set(sig.values())) == 1:
            culprits = sorted({
                f"{r['dialogue']}T{r['turn']}"
                for rs in by.values() for r in rs if not r["schema_ok"]
            })
            fast = [
                r for rs in by.values() for r in rs
                if not r["schema_ok"] and r.get("latency_ms", 9999) < 400
            ]
            out.append(
                "> 🚨 **這張表沒有鑑別度**：所有受測模型的三個比率完全相同"
                f"（{sig[next(iter(sig))]}）。跨臂一致代表輸出不是模型產生的——"
                f"失分集中在 {'、'.join(culprits) or '(無)'}"
                + (f"，其中 {len(fast)} 筆延遲 < 400ms（模型未被呼叫，"
                   "多半是防護攔截或快取）" if fast else "")
                + "。修掉共同成因後重跑才有意義。\n"
            )

    text = "\n".join(out)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"\n已寫入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
