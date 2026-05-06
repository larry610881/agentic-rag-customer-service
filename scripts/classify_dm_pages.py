"""家樂福 DM page-type classifier.

用 Claude Haiku 4.5 對每頁做輕量 vision 分類，驗證 detection 機制
可靠度，作為「OCR prompt routing」設計的 baseline。

輸出：
- /tmp/dm-pages/classification.csv  (page_no, type, confidence, evidence)
- stdout 印出類型 → 頁數聚合表

Usage:
    cd apps/backend
    uv run python ../../scripts/classify_dm_pages.py
"""
from __future__ import annotations

import asyncio
import base64
import csv
import json
import pathlib
import re
import sys
import time

import anthropic

from src.config import settings

PAGES_DIR = pathlib.Path("/tmp/dm-pages")
CSV_OUT = PAGES_DIR / "classification.csv"
MODEL = "claude-haiku-4-5-20251001"
CONCURRENCY = 6

PROMPT = """這是家樂福 DM 的某一頁圖片。請分類為下列**其中一種**：

- product_catalog: 商品列表頁（具體商品照 + 價格 + 商品名，目的是賣商品）
- promotion_only: 純優惠/服務介紹頁（信用卡聯名卡 / 會員活動 / 折扣券 / 滿額禮 / 線上購物導覽 / 服務介紹，無具體商品列表，或商品只是裝飾性配圖）
- cover_or_index: 封面 / 目錄 / 結尾 / 店鋪營業時間 / 加油站資訊
- mixed: 混合頁（明顯同時有商品列表 + 大塊優惠/活動條款）

回應格式：嚴格 JSON 一行，不要 markdown fence、不要解釋：
{"page_type": "product_catalog|promotion_only|cover_or_index|mixed", "confidence": 0.0~1.0, "evidence": "20 字內中文敘述判斷依據"}
"""


def _strip_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n", "", s)
        s = re.sub(r"\n```$", "", s.strip())
    return s.strip()


async def classify_one(
    client: anthropic.AsyncAnthropic,
    png: pathlib.Path,
    sem: asyncio.Semaphore,
) -> dict:
    page_no = int(png.stem.split("_")[1])
    img_b64 = base64.b64encode(png.read_bytes()).decode("ascii")

    async with sem:
        for attempt in range(3):
            try:
                msg = await client.messages.create(
                    model=MODEL,
                    max_tokens=200,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": img_b64,
                                },
                            },
                            {"type": "text", "text": PROMPT},
                        ],
                    }],
                )
                raw = _strip_fence(msg.content[0].text)
                data = json.loads(raw)
                return {
                    "page_no": page_no,
                    "page_type": data.get("page_type", "unknown"),
                    "confidence": float(data.get("confidence", 0.0)),
                    "evidence": data.get("evidence", ""),
                }
            except (anthropic.APIError, json.JSONDecodeError) as e:
                if attempt == 2:
                    return {
                        "page_no": page_no,
                        "page_type": "error",
                        "confidence": 0.0,
                        "evidence": f"{type(e).__name__}: {str(e)[:60]}",
                    }
                await asyncio.sleep(2 ** attempt)
    return {"page_no": page_no, "page_type": "error", "confidence": 0.0, "evidence": "unreachable"}


async def main() -> int:
    api_key = settings.anthropic_api_key
    if not api_key:
        print("[fail] ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    pngs = sorted(PAGES_DIR.glob("page_*.png"))
    if not pngs:
        print(f"[fail] no PNGs in {PAGES_DIR}", file=sys.stderr)
        return 1

    print(f"classifying {len(pngs)} pages with {MODEL} (concurrency={CONCURRENCY})...")
    t0 = time.monotonic()

    client = anthropic.AsyncAnthropic(api_key=api_key)
    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = [classify_one(client, p, sem) for p in pngs]
    results = await asyncio.gather(*tasks)

    results.sort(key=lambda r: r["page_no"])
    elapsed = time.monotonic() - t0
    print(f"done in {elapsed:.1f}s")

    # CSV
    with CSV_OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["page_no", "page_type", "confidence", "evidence"]
        )
        w.writeheader()
        w.writerows(results)
    print(f"\nwrote {CSV_OUT}")

    # Summary
    by_type: dict[str, list[int]] = {}
    for r in results:
        by_type.setdefault(r["page_type"], []).append(r["page_no"])

    print("\n=== 類型 → 頁數聚合 ===")
    order = ["product_catalog", "mixed", "promotion_only", "cover_or_index", "error", "unknown"]
    for t in order:
        if t in by_type:
            pages = by_type[t]
            print(f"  {t:18s} ({len(pages):3d} 頁): {pages}")
    for t in by_type:
        if t not in order:
            print(f"  {t:18s} ({len(by_type[t]):3d} 頁): {by_type[t]}")

    print("\n=== 低 confidence (< 0.7) ===")
    low = [r for r in results if r["confidence"] < 0.7]
    for r in low:
        print(f"  page {r['page_no']:2d}: {r['page_type']:18s} conf={r['confidence']:.2f}  {r['evidence']}")
    if not low:
        print("  (none — detector 對全部 64 頁信心 ≥ 0.7)")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
