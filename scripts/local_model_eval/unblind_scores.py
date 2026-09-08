#!/usr/bin/env python3
"""揭盲：把盲評 session 填好的 評分表.csv 用對照表還原成每個模型的成績。

盲評包裡的代號是「每一輪獨立指派」的，所以一定要靠對照表才聚合得回來。
輸出：各模型三個維度的平均與總分、依難度層與對話分組、以及扣分最多的題目清單。

用法：
  python3 scripts/local_model_eval/unblind_scores.py \\
      --scores ~/qa-scoring/評分表.csv \\
      --key-file scripts/local_model_eval/results/blind_key_20260908.json \\
      --results scripts/local_model_eval/results/main60_20260908-1530.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

DIMS = ["正確性", "忠實度", "格式"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True)
    ap.add_argument("--key-file", required=True)
    ap.add_argument("--results", default=[], nargs="*",
                    help="給了就一起輸出延遲與 token 統計；可給多個檔")
    args = ap.parse_args()

    key = json.loads(Path(args.key_file).expanduser().read_text(encoding="utf-8"))
    mapping = key["mapping"]

    per_bot: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    per_tier: dict[tuple, list] = defaultdict(list)
    lows: list[tuple] = []
    missing = 0

    with Path(args.scores).expanduser().open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            cell, label = row["cell_id"].strip(), row["代號"].strip()
            if cell not in mapping or label not in mapping[cell]:
                missing += 1
                continue
            bot = mapping[cell][label]
            vals = {}
            for d in DIMS:
                raw = (row.get(d) or "").strip()
                if raw == "":
                    missing += 1
                    vals = {}
                    break
                vals[d] = int(raw)
            if not vals:
                continue
            for d in DIMS:
                per_bot[bot][d].append(vals[d])
            total = sum(vals.values())
            per_bot[bot]["總分"].append(total)
            tier = cell.split("-")[0][0]     # E / M / H
            per_tier[(bot, tier)].append(total)
            if total <= 3:
                lows.append((cell, bot, total, (row.get("備註") or "").strip()))

    if not per_bot:
        print("沒有讀到任何有效評分，檢查 cell_id 與對照表是否成對")
        return 1

    print("## 各模型平均（每輪滿分 6）\n")
    print("| 模型 | 正確性 | 忠實度 | 格式 | 總分 | 輪數 |")
    print("|---|---|---|---|---|---|")
    for bot in sorted(per_bot, key=lambda b: -sum(per_bot[b]["總分"]) / max(1, len(per_bot[b]["總分"]))):
        s = per_bot[bot]
        n = len(s["總分"])
        cols = " | ".join(f"{sum(s[d]) / n:.2f}" for d in DIMS)
        print(f"| {bot} | {cols} | {sum(s['總分']) / n:.2f} | {n} |")

    print("\n## 依難度層平均總分\n")
    tiers = sorted({t for _, t in per_tier})
    print("| 模型 | " + " | ".join({"E": "簡單", "M": "中等", "H": "難"}.get(t, t) for t in tiers) + " |")
    print("|---" * (len(tiers) + 1) + "|")
    for bot in sorted(per_bot):
        cells = []
        for t in tiers:
            v = per_tier.get((bot, t), [])
            cells.append(f"{sum(v) / len(v):.2f}" if v else "-")
        print(f"| {bot} | " + " | ".join(cells) + " |")

    if lows:
        print("\n## 失分最重的輪次（總分 ≤ 3）\n")
        for cell, bot, total, note in sorted(lows, key=lambda x: x[2])[:30]:
            print(f"- `{cell}` {bot} → {total}/6　{note}")

    if args.results:
        rows = [
            json.loads(x)
            for f in args.results
            for x in Path(f).read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
        agg: dict[str, list] = defaultdict(list)
        for r in rows:
            agg[r["bot"]].append(r)
        # 串流不下發 usage，jsonl 的 output_tokens 對 Gemini 是 chunk 數
        # （chunk/token ≈ 0.03），直接印會低估 30 倍。改用回答文字配 tiktoken
        # 估算，跟 build_report.py 同一把尺——只能跨模型比快慢，不能算錢。
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            enc = None
        print("\n## 效能（不參與評分，揭盲後才對照；中位數）\n")
        head = "| 模型 | 首 token ms | 總時間 ms | 字元/秒 |"
        head += " 估算 token/秒 |" if enc else ""
        print(head)
        print("|---|---|---|---|" + ("---|" if enc else ""))
        for bot, rs in sorted(agg.items()):
            rs = [x for x in rs if x.get("ttft_ms") and x.get("latency_ms")]
            if not rs:
                continue
            med = lambda xs: statistics.median(xs)  # noqa: E731
            gen = [max(1, x["latency_ms"] - x["ttft_ms"]) for x in rs]
            txt = [x.get("answer") or "" for x in rs]
            cps = [len(t) / (g / 1000) for t, g in zip(txt, gen)]
            line = (f"| {bot} | {med([x['ttft_ms'] for x in rs]):.0f} | "
                    f"{med([x['latency_ms'] for x in rs]):.0f} | {med(cps):.0f} |")
            if enc:
                tps = [len(enc.encode(t)) / (g / 1000) for t, g in zip(txt, gen)]
                line += f" {med(tps):.0f} |"
            print(line)
        if not enc:
            print("\n（tiktoken 不在環境中，略過 token/秒；字元/秒仍可跨模型比較）")

    if missing:
        print(f"\n（有 {missing} 列因為欄位空白或對不到代號被略過）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
