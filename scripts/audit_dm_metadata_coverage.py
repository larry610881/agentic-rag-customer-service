"""DM-level metadata coverage audit.

對每頁 PNG 用 Claude Vision 問「圖片上是否印有：
  - 活動期間 / DM 期間（YYYY/MM/DD 或 X/X～X/X 區間）
  - 限定星期幾 / 每月 / 每週活動
  - 會員 / 持卡人專屬條件
  - 商家標示（如「家樂福」「中國信託」）
  - 整頁性折扣（滿額禮、單筆消費條件、回饋上限）
」

然後撈 dev-vm 上該頁所有 chunks 的 content，比對是否抽到。

輸出 docs/dm-baseline-and-after/metadata_audit.md 含：
  - 每頁 has_in_image vs has_in_chunks 表
  - 漏抽頁清單（圖片有但 chunks 沒）— root cause 推測

Usage:
    cd apps/backend
    uv run python ../../scripts/audit_dm_metadata_coverage.py \\
        --pages-dir /tmp/dm-pages \\
        --kb-id 559538a4-d2ac-46e8-8e2c-1d04b599d7e6 \\
        --output ../../docs/dm-baseline-and-after/metadata_audit.md
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import pathlib
import re
import subprocess
import sys
import time

import anthropic

from src.config import settings

MODEL = "claude-haiku-4-5-20251001"
CONCURRENCY = 6

AUDIT_PROMPT = """你是 DM 圖片 metadata 審計員。請仔細看這頁，判斷以下五類資訊**是否印在圖片上**，回嚴格 JSON：

{
  "date_range": true|false,        // 圖片上印有日期區間（YYYY/MM/DD 或 4/8~4/30 縮寫格式）
  "weekday_event": true|false,     // 圖片上印有限定星期/每月/每週活動（如「週二加油日」「每月X號」）
  "member_only": true|false,       // 圖片上印有會員 / 持卡人 / APP 用戶專屬條件
  "merchant_brand": true|false,    // 圖片上印有商家品牌（家樂福、中國信託等）
  "page_level_promo": true|false,  // 圖片上印有整頁性活動（滿額折扣、單筆消費門檻、回饋上限）
  "evidence": "10 字內中文敘述判斷依據"
}

只回 JSON，不要 markdown fence、不要解釋。"""


# 把 audit 結果跟 chunks content 比對的 keyword
CHUNK_KEYWORDS = {
    "date_range": (
        re.compile(r"20[0-9]{2}/[0-9]{1,2}/[0-9]{1,2}"),  # YYYY/MM/DD
        re.compile(r"[0-9]{1,2}/[0-9]{1,2}.{0,3}~.{0,3}[0-9]{1,2}/[0-9]{1,2}"),  # 4/8~4/30
        re.compile(r"活動期間"),
        re.compile(r"DM 期間|DM期間"),
    ),
    "weekday_event": (
        re.compile(r"週[一二三四五六日]"),
        re.compile(r"星期[一二三四五六日]"),
        re.compile(r"每月"),
        re.compile(r"每週"),
    ),
    "member_only": (
        re.compile(r"會員"),
        re.compile(r"持卡人"),
        re.compile(r"APP\s*用戶|App\s*用戶"),
        re.compile(r"unipen|UniOpen", re.IGNORECASE),
    ),
    "merchant_brand": (
        re.compile(r"家樂福"),
        re.compile(r"Carrefour", re.IGNORECASE),
        re.compile(r"中國信託"),
    ),
    "page_level_promo": (
        re.compile(r"滿\s*[$]?[0-9]"),
        re.compile(r"單筆消費"),
        re.compile(r"回饋上限"),
        re.compile(r"折\s*[0-9]"),
        re.compile(r"頁面級促銷"),
    ),
}


def _strip_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n", "", s)
        s = re.sub(r"\n```$", "", s.strip())
    return s.strip()


async def audit_page_image(
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
                    max_tokens=300,
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
                            {"type": "text", "text": AUDIT_PROMPT},
                        ],
                    }],
                )
                raw = _strip_fence(msg.content[0].text)
                data = json.loads(raw)
                data["page_no"] = page_no
                return data
            except (anthropic.APIError, json.JSONDecodeError):
                if attempt == 2:
                    return {
                        "page_no": page_no, "date_range": False,
                        "weekday_event": False, "member_only": False,
                        "merchant_brand": False, "page_level_promo": False,
                        "evidence": "(audit failed)",
                    }
                await asyncio.sleep(2 ** attempt)
    return {"page_no": page_no}  # unreachable


def fetch_chunks_from_devvm(kb_id: str) -> dict[int, list[str]]:
    """SSH 到 dev-vm 撈 KB 全部 chunks，回 page_no -> [content,...]."""
    cmd = [
        "/home/p10359945/google-cloud-sdk/bin/gcloud",
        "compute", "ssh", "db-services",
        "--zone=asia-east1-b",
        "--tunnel-through-iap",
        "--project=project-4dc6cadb-5d47-4482-a32",
        "--command=docker exec agentic-rag-db psql -U postgres -d agentic_rag "
        f"-tA -F '|||' -c \"SELECT d.page_number, c.content FROM chunks c "
        f"JOIN documents d ON d.id = c.document_id "
        f"WHERE d.kb_id = '{kb_id}' AND d.parent_id IS NOT NULL "
        f"ORDER BY d.page_number, c.chunk_index;\"",
    ]
    print("fetching chunks from dev-vm...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"[fail] gcloud SSH error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    by_page: dict[int, list[str]] = {}
    for line in result.stdout.splitlines():
        # filter out gcloud warning lines
        parts = line.split("|||", 1)
        if len(parts) != 2:
            continue
        try:
            page_no = int(parts[0])
        except ValueError:
            continue
        by_page.setdefault(page_no, []).append(parts[1])
    return by_page


def chunks_have_keyword(chunks: list[str], category: str) -> bool:
    patterns = CHUNK_KEYWORDS[category]
    text = "\n".join(chunks)
    return any(p.search(text) for p in patterns)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages-dir", default="/tmp/dm-pages")
    ap.add_argument("--kb-id", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--audit-cache", default="/tmp/dm-pages/metadata_audit.json")
    args = ap.parse_args()

    api_key = settings.anthropic_api_key
    if not api_key:
        print("[fail] ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1

    pngs = sorted(pathlib.Path(args.pages_dir).glob("page_*.png"))
    if not pngs:
        print("[fail] no PNGs", file=sys.stderr)
        return 1

    # Audit images（cached — re-run 不重 call）
    cache_path = pathlib.Path(args.audit_cache)
    if cache_path.exists():
        print(f"loading audit cache: {cache_path}")
        audits = json.loads(cache_path.read_text())
    else:
        print(f"auditing {len(pngs)} images...")
        client = anthropic.AsyncAnthropic(api_key=api_key)
        sem = asyncio.Semaphore(CONCURRENCY)
        t0 = time.monotonic()
        audits_list = await asyncio.gather(
            *[audit_page_image(client, p, sem) for p in pngs]
        )
        audits = {str(a["page_no"]): a for a in audits_list}
        cache_path.write_text(json.dumps(audits, ensure_ascii=False, indent=2))
        print(f"  done in {time.monotonic()-t0:.1f}s, cached")

    # Fetch chunks
    chunks_by_page = fetch_chunks_from_devvm(args.kb_id)

    # Compare
    categories = ["date_range", "weekday_event", "member_only",
                  "merchant_brand", "page_level_promo"]
    rows: list[dict] = []
    for png in pngs:
        page_no = int(png.stem.split("_")[1])
        a = audits.get(str(page_no), {})
        chunks = chunks_by_page.get(page_no, [])
        row: dict = {"page_no": page_no, "chunks": len(chunks)}
        for cat in categories:
            in_image = bool(a.get(cat, False))
            in_chunks = chunks_have_keyword(chunks, cat)
            row[cat + "_img"] = in_image
            row[cat + "_db"] = in_chunks
            row[cat + "_gap"] = in_image and not in_chunks
        row["evidence"] = a.get("evidence", "")
        rows.append(row)

    # Summary
    summary: dict[str, dict[str, int]] = {}
    for cat in categories:
        summary[cat] = {
            "img_count": sum(1 for r in rows if r[cat + "_img"]),
            "db_count": sum(1 for r in rows if r[cat + "_db"]),
            "gap_count": sum(1 for r in rows if r[cat + "_gap"]),
        }
        summary[cat]["gap_pages"] = [
            r["page_no"] for r in rows if r[cat + "_gap"]
        ]

    # Render markdown
    out: list[str] = []
    out.append("# DM Metadata Coverage Audit\n")
    out.append(f"**KB**: `{args.kb_id}`")
    out.append(f"**Total pages audited**: {len(pngs)}")
    out.append(
        f"**Total chunks scanned**: {sum(len(v) for v in chunks_by_page.values())}\n"
    )
    out.append("\n## 缺失統計（圖片有印 vs DB chunks 沒抽到）\n")
    out.append("| Category | 圖片有印 | DB 抽到 | **漏抽頁數** | 漏抽頁碼 |")
    out.append("|---|---|---|---|---|")
    for cat in categories:
        s = summary[cat]
        gap_str = ", ".join(str(p) for p in s["gap_pages"][:30])
        if len(s["gap_pages"]) > 30:
            gap_str += f" ...（共 {len(s['gap_pages'])} 頁）"
        out.append(
            f"| `{cat}` | {s['img_count']} | {s['db_count']} | "
            f"**{s['gap_count']}** | {gap_str or '—'} |"
        )

    out.append("\n## 完整對照表（每頁五類）\n")
    out.append(
        "| Page | chunks | date_range | weekday | member | merchant | "
        "page_promo | evidence |"
    )
    out.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        def cell(cat: str) -> str:
            i = r[cat + "_img"]
            d = r[cat + "_db"]
            if i and d:
                return "✅"
            if i and not d:
                return "🔴 漏抽"
            if not i and d:
                return "✓"
            return "—"
        out.append(
            f"| **{r['page_no']}** | {r['chunks']} "
            f"| {cell('date_range')} | {cell('weekday_event')} "
            f"| {cell('member_only')} | {cell('merchant_brand')} "
            f"| {cell('page_level_promo')} | {r['evidence'][:30]} |"
        )

    out.append("\n## 圖例\n")
    out.append("- ✅ 圖片有印 + DB 有抽")
    out.append("- 🔴 圖片有印但 DB 漏抽（**OCR prompt 改進目標**）")
    out.append("- ✓ DB 有但圖片沒判斷有（可能 LLM 誤判，少見）")
    out.append("- — 圖片沒印 + DB 沒抽（不是問題）")

    pathlib.Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.output).write_text("\n".join(out), encoding="utf-8")
    print(f"\nwrote {args.output}")

    # Stdout summary
    print("\n=== 漏抽統計 ===")
    for cat in categories:
        s = summary[cat]
        print(
            f"  {cat:18s}: 圖片有 {s['img_count']:3d} 頁, "
            f"DB 有 {s['db_count']:3d} 頁, "
            f"**漏抽 {s['gap_count']:3d} 頁**"
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
