"""Convert pipe-delimited baseline_raw.txt → markdown 報告。

Input:  /tmp/baseline_raw.txt（從 dev-vm psql -tA -F '|' 撈出）
Output: docs/dm-baseline-and-after/<label>.md
"""
from __future__ import annotations

import argparse
import pathlib
from collections import defaultdict


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/tmp/baseline_raw.txt")
    ap.add_argument("--output", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument(
        "--detector-classifications",
        default="2:promotion,3:promotion,4:mixed,6:mixed,8:promotion,"
                "9:mixed,10:promotion,11:promotion,47:mixed,64:promotion",
        help="page:type 對應，逗號分隔（從 64 頁分類器結果取）",
    )
    args = ap.parse_args()

    detector_map = dict(
        item.split(":") for item in args.detector_classifications.split(",")
    )

    raw = pathlib.Path(args.input).read_text(encoding="utf-8")
    by_page: dict[int, dict] = defaultdict(
        lambda: {"docs": {}, "chunks": defaultdict(dict)}
    )

    for line in raw.splitlines():
        line = line.strip()
        # gcloud SSH 會把 WARNING 等行混進來，過濾 pipe-delimited 9-column 才是資料行
        parts = line.split("|")
        if len(parts) != 9:
            continue
        try:
            page_no = int(parts[0])
        except ValueError:
            continue
        doc_id, filename, status, chunk_count, updated_at = parts[1:6]
        chunk_index_str, chunk_id, content = parts[6:9]

        by_page[page_no]["docs"][doc_id] = {
            "filename": filename,
            "status": status,
            "chunk_count": chunk_count,
            "updated_at": updated_at,
        }
        if chunk_index_str:
            by_page[page_no]["chunks"][doc_id][int(chunk_index_str)] = {
                "id": chunk_id,
                "content": content.replace("\\n", "\n"),
            }

    out: list[str] = []
    out.append(f"# DM baseline / after dump — label=`{args.label}`\n")
    out.append("**KB**: `559538a4-d2ac-46e8-8e2c-1d04b599d7e6` (家樂福DM)")
    out.append(
        f"**Pages dumped**: {sorted(by_page.keys())}（共 {len(by_page)} 頁）"
    )
    out.append("")
    out.append("頁面類型由 `scripts/classify_dm_pages.py` Haiku 4.5 分類器判定。\n")

    for page_no in sorted(by_page.keys()):
        page = by_page[page_no]
        detector_type = detector_map.get(str(page_no), "?")
        out.append(f"\n---\n\n## Page {page_no} — detector: `{detector_type}`\n")

        for doc_id, meta in page["docs"].items():
            chunks = page["chunks"][doc_id]
            out.append(
                f"### child doc `{doc_id[:8]}...`  filename=`{meta['filename']}`"
            )
            out.append(
                f"- status=`{meta['status']}` chunk_count="
                f"`{meta['chunk_count']}` (actual: {len(chunks)})"
            )
            out.append(f"- updated_at: {meta['updated_at']}")
            out.append("")

            if not chunks:
                out.append("_(no chunks — 可能 process failed)_\n")
                continue

            for idx in sorted(chunks.keys()):
                ch = chunks[idx]
                out.append(f"#### chunk #{idx} (id=`{ch['id'][:8]}...`)\n")
                out.append("```")
                out.append(ch["content"])
                out.append("```")
                out.append("")

    out_path = pathlib.Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {out_path} ({sum(len(s) for s in out):,} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
