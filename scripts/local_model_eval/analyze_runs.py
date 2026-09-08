#!/usr/bin/env python3
"""多輪重跑結果分析 —— 穩定度、效能、以及「值得補跑的題目」清單。

為什麼要看穩定度而不只看平均分：重跑同一份題組**不會**增加「推廣到所有客服問題」
的統計力，它只告訴你模型在這些題上穩不穩。所以這支腳本的重點不是再算一次平均，
而是找出**會翻動的題目**——資訊都在那裡，後續只要針對那幾題加跑就好，不必整份重跑。

輸出三塊：
1. 效能：首 token、總時間、字元/秒、估算 token/秒（tiktoken 對所有模型用同一把尺，
   只能跨模型比快慢，**不能拿來算錢**——算錢要用非串流那份的真實 output_tokens）
2. 穩定度：同一題在多次執行之間，金標準數字覆蓋是否一致
3. 翻動題清單：建議針對這些題目加跑

用法：
  python3 scripts/local_model_eval/analyze_runs.py \\
      --results scripts/local_model_eval/results/main60_<時間>.jsonl [--out 報告.md]
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


def gold_facts(gold: str) -> set[str]:
    return {
        m.group(0).rstrip(".、，,")
        for m in NUM.finditer(gold or "")
        if len(m.group(0).rstrip(".、，,")) >= 2
    }


def covered(gold: str, answer: str) -> frozenset[str]:
    a = (answer or "").replace(",", "").replace("，", "")
    return frozenset(k for k in gold_facts(gold) if k.replace(",", "") in a)


def _encoder():
    """取 tiktoken 編碼器；沒有就回 None。

    **不做「退回字元數」的靜默替代**——那會讓「字元/秒」與「token/秒」兩欄變成
    同一個數字，看起來像兩個獨立指標，其實是同一個。寧可少一欄也不要假的一欄。
    """
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    rows = [
        json.loads(x)
        for x in Path(args.results).read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    ok = [r for r in rows if r.get("ok")]
    enc = _encoder()
    out: list[str] = []

    runs = sorted({r.get("run", 1) for r in rows})
    out.append(f"# 多輪結果分析\n")
    out.append(f"檔案：`{Path(args.results).name}`　列數 {len(rows)}　"
               f"成功 {len(ok)}　執行次數 {len(runs)}\n")

    fails = [r for r in rows if not r.get("ok")]
    if fails:
        by_bot = defaultdict(int)
        for r in fails:
            by_bot[r["bot"]] += 1
        out.append("⚠️ 失敗列：" + "、".join(f"{b}×{n}" for b, n in sorted(by_bot.items())) + "\n")

    # --- 1. 效能 ---
    perf = defaultdict(list)
    for r in ok:
        if not r.get("ttft_ms"):
            continue
        gen_ms = max(1, r["latency_ms"] - r["ttft_ms"])
        txt = r.get("answer") or ""
        ntok = len(enc.encode(txt)) / (gen_ms / 1000) if enc else None
        perf[r["bot"]].append((r["ttft_ms"], r["latency_ms"],
                               len(txt) / (gen_ms / 1000), ntok))
    if perf:
        out.append("## 效能（中位數）\n")
        if enc:
            out.append("token 估算用 tiktoken cl100k（所有模型同一把尺，只能跨模型比快慢，"
                       "**不可拿來算錢**——算錢要用非串流那份的真實 output_tokens）。\n")
            out.append("| 模型 | n | 首 token ms | 總時間 ms | 字元/秒 | 估算 token/秒 |")
            out.append("|---|---|---|---|---|---|")
        else:
            out.append("⚠️ 找不到 tiktoken，略過 token/秒 這一欄"
                       "（要它就用 `cd apps/backend && uv run python ../../scripts/...` 執行）。\n")
            out.append("| 模型 | n | 首 token ms | 總時間 ms | 字元/秒 |")
            out.append("|---|---|---|---|---|")
        for b, v in sorted(perf.items(), key=lambda kv: statistics.median(x[1] for x in kv[1])):
            m = lambda i: statistics.median(x[i] for x in v)  # noqa: E731
            cells_ = [b, str(len(v)), f"{m(0):.0f}", f"{m(1):.0f}", f"{m(2):.0f}"]
            if enc:
                cells_.append(f"{m(3):.0f}")
            out.append("| " + " | ".join(cells_) + " |")

    # --- 2. 穩定度 ---
    cells: dict[tuple, list] = defaultdict(list)
    for r in ok:
        cells[(r["bot"], r["dialogue"], r["turn"])].append(r)

    stab = defaultdict(lambda: [0, 0])
    flips: list[tuple] = []
    for (bot, d, t), rs in cells.items():
        if len(rs) < 2 or not gold_facts(rs[0]["gold"]):
            continue
        sets = {covered(x["gold"], x["answer"]) for x in rs}
        stab[bot][0] += 1
        if len(sets) > 1:
            stab[bot][1] += 1
            union = set().union(*sets)
            inter = set.intersection(*[set(s) for s in sets])
            flips.append((bot, d, t, len(rs), sorted(union - inter)))

    if stab:
        out.append("\n## 穩定度（同題多次執行，金標準數字覆蓋是否一致）\n")
        out.append("| 模型 | 可比題數 | 會翻動 | 翻動率 |")
        out.append("|---|---|---|---|")
        for b, (n, f) in sorted(stab.items(), key=lambda kv: kv[1][1] / max(1, kv[1][0])):
            out.append(f"| {b} | {n} | {f} | {f / n * 100:.0f}% |")

    if flips:
        out.append("\n## 建議加跑的題目（會翻動者，資訊都在這些題上）\n")
        out.append("| 模型 | 題目 | 執行次數 | 不穩定的事實 |")
        out.append("|---|---|---|---|")
        for bot, d, t, n, diff in sorted(flips, key=lambda x: (x[0], x[1], x[2])):
            out.append(f"| {bot} | {d}-{t} | {n} | {', '.join(diff[:6]) or '（措辭差異）'} |")
        ids = sorted({f"{d}" for _, d, _, _, _ in flips})
        out.append(f"\n加跑指令：`--only {','.join(ids)} --repeat 10`")

    text = "\n".join(out)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"\n已寫入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
