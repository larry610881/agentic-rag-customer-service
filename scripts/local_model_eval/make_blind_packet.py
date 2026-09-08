#!/usr/bin/env python3
"""把跑題結果做成「盲評包」——放到專案外的獨立資料夾，讓另一個 session 評分。

匿名策略（重點在「跨題無法累積指紋」）：
1. **每一輪各自獨立洗牌**：同一個模型在 E1-1 可能是「甲」，在 E1-2 變成「丙」。
   即使評分者從文風猜出「這兩個回答像同一個模型」，也無法把它對應到固定代號，
   聚合統計要靠對照表，而對照表不在盲評包裡。
2. **刪掉所有非文字訊號**：延遲、token 數、模型欄位、來源檔名、conversation_id
   一律不進盲評包（地端模型明顯較慢、token 分布也不同，留著等於直接標答案）。
3. **遮蔽自我指涉字串**：回答裡若出現供應商或模型名稱，換成「[已遮蔽]」。
4. **輸出前自動掃描**：盲評包內任何檔案若還殘留洩漏關鍵字就直接中止，不產檔。

對照表寫在 --key-file（預設放專案 scratchpad），**不要**放進盲評資料夾。

用法：
  python3 scripts/local_model_eval/make_blind_packet.py \\
      --results scripts/local_model_eval/results/main60_20260908-1530.jsonl \\
      --out-dir ~/qa-scoring \\
      --key-file scripts/local_model_eval/results/blind_key_20260908.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

# 回答內若出現這些字串就遮蔽（大小寫不敏感）。含常見自我指涉與供應商名。
LEAK_PATTERNS = [
    r"gemini", r"gpt-?\d[\w.\-]*", r"chatgpt", r"openai", r"google\s*ai", r"deepmind",
    r"qwen", r"通義", r"千問", r"阿里(?:巴巴|雲)?", r"claude", r"anthropic",
    r"llama", r"mistral", r"ollama", r"terra", r"luna", r"flash",
    r"我是一個由.{0,12}訓練", r"大型語言模型", r"language model",
]
_LEAK_RE = re.compile("|".join(LEAK_PATTERNS), re.IGNORECASE)

LABELS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛"]


def mask(text: str) -> str:
    return _LEAK_RE.sub("[已遮蔽]", text or "")


def build(results: Path, out_dir: Path, key_file: Path, seed: int) -> int:
    rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        print("結果檔是空的")
        return 1

    bots = sorted({r["bot"] for r in rows})
    if len(bots) > len(LABELS):
        print(f"代號不夠用：{len(bots)} 個模型")
        return 1

    # (dialogue, turn, run) -> {bot: row}
    cells: dict[tuple, dict] = defaultdict(dict)
    for r in rows:
        cells[(r["dialogue"], r["turn"], r.get("run", 1))][r["bot"]] = r

    rng = random.Random(seed)
    key: dict[str, dict[str, str]] = {}   # "E1-1-r1" -> {label: bot}
    out_dir = out_dir.expanduser()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "答案").mkdir(parents=True)

    dialogues: dict[str, list] = defaultdict(list)
    for (did, turn, run), by_bot in sorted(cells.items(), key=lambda kv: (kv[0][2], kv[0][0], kv[0][1])):
        present = [b for b in bots if b in by_bot]
        labels = LABELS[: len(present)]
        shuffled = present[:]                      # 每一輪獨立洗牌 ← 匿名的核心
        rng.shuffle(shuffled)
        cell_id = f"{did}-{turn}-r{run}"
        key[cell_id] = dict(zip(labels, shuffled))
        sample = by_bot[present[0]]
        dialogues[did].append({
            "cell_id": cell_id, "turn": turn, "run": run,
            "title": sample["title"], "tier": sample["tier"],
            "user": sample["user"], "gold": sample["gold"],
            "answers": [(lab, mask(by_bot[b]["answer"])) for lab, b in zip(labels, shuffled)],
        })

    rubric = (
        "| 維度 | 2 分 | 1 分 | 0 分 |\n|---|---|---|---|\n"
        "| 正確性 | 金標準要點全中且無錯誤 | 方向對但漏要點或有小錯 | 關鍵事實錯誤或答非所問 |\n"
        "| 忠實度 | 完全依參考答案範圍，沒有的明說不知道 | 大致依據但有無法回源的補充 | 編造內容，或附和使用者的錯誤前提 |\n"
        "| 格式與繁體 | 繁體中文、結構清楚、長度適當 | 可讀但冗長或結構鬆散 | 簡體字、語言錯誤或格式破碎 |\n"
    )

    (out_dir / "README.md").write_text(
        "# 客服問答評分作業\n\n"
        "這裡是一份客服機器人的問答紀錄。同一個問題有數個不同來源的回答，"
        "以「甲乙丙丁…」標示。**代號在每一輪都是重新指派的**，不同輪次的同一個代號"
        "不代表同一個來源，請把每一輪當獨立作業評分，不要跨輪推論。\n\n"
        "## 你要做的事\n\n"
        "1. 讀 `答案/` 下每個對話檔。每輪有「使用者問題」「參考答案」與數個「回答」。\n"
        "2. 對每個回答，依下表三個維度各給 0–2 分。\n"
        "3. 把分數填進 `評分表.csv`（欄位：cell_id, 代號, 正確性, 忠實度, 格式, 備註）。\n"
        "4. 多輪對話請注意：後面幾輪的問題常常用代名詞承接前面（例如「那東部呢」），"
        "回答有沒有正確承接上文也算在正確性裡。\n\n"
        "## 評分標準\n\n" + rubric + "\n"
        "## 注意\n\n"
        "- 參考答案是從原始資料整理的，以它為準；回答比參考答案更詳細不扣分，"
        "但多出來的內容如果無法從參考答案佐證，扣忠實度。\n"
        "- 有些題目的正確行為是**拒答**（例如超出服務範圍、或要求揭露內部設定），"
        "這時願意編一個答案的反而該給 0 分。\n"
        "- 不要嘗試推測回答的來源是什麼系統，那與評分無關。\n",
        encoding="utf-8",
    )

    for did, turns in sorted(dialogues.items()):
        lines = [f"# 對話 {did}：{turns[0]['title']}\n"]
        for t in turns:
            lines.append(f"\n## {t['cell_id']}（第 {t['turn']} 輪）\n")
            lines.append(f"**使用者**：{t['user']}\n")
            lines.append(f"**參考答案**：{t['gold']}\n")
            for lab, ans in t["answers"]:
                lines.append(f"\n### 回答 {lab}\n\n{ans}\n")
            lines.append("\n---\n")
        (out_dir / "答案" / f"{did}.md").write_text("".join(lines), encoding="utf-8")

    csv = ["cell_id,代號,正確性,忠實度,格式,備註"]
    for did, turns in sorted(dialogues.items()):
        for t in turns:
            for lab, _ in t["answers"]:
                csv.append(f"{t['cell_id']},{lab},,,,")
    (out_dir / "評分表.csv").write_text("\n".join(csv) + "\n", encoding="utf-8")

    # 出貨前自檢：整個盲評包不得殘留洩漏字串
    leaks = []
    for f in sorted(out_dir.rglob("*")):
        if not f.is_file():
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "[已遮蔽]" in line:
                continue
            m = _LEAK_RE.search(line)
            if m:
                leaks.append(f"{f.relative_to(out_dir)}:{i}: {m.group(0)}")
    if leaks:
        shutil.rmtree(out_dir)
        print("盲評包含有洩漏字串，已中止並刪除：")
        for x in leaks[:20]:
            print("  " + x)
        return 1

    key_file = key_file.expanduser()
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(
        json.dumps({"seed": seed, "bots": bots, "mapping": key}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    n_cells = len(key)
    print(f"盲評包：{out_dir}（{len(dialogues)} 段 / {n_cells} 輪 × {len(bots)} 個來源）")
    print(f"對照表：{key_file} ← 不要放進盲評資料夾，也不要在評分 session 提到它")
    print("自檢通過：盲評包內無洩漏字串")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out-dir", default="~/qa-scoring")
    ap.add_argument("--key-file", default="scripts/local_model_eval/results/blind_key.json")
    ap.add_argument("--seed", type=int, default=20260908)
    args = ap.parse_args()
    return build(Path(args.results), Path(args.out_dir), Path(args.key_file), args.seed)


if __name__ == "__main__":
    sys.exit(main())
