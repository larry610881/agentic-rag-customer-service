"""Dump 指定 KB + page_number 的 OCR chunks 為 markdown，用於 reprocess
前後 baseline 比對。

用法（從 apps/backend 執行）：
    cd apps/backend
    uv run python ../../scripts/dump_dm_page_chunks.py \\
        --kb-id 559538a4-d2ac-46e8-8e2c-1d04b599d7e6 \\
        --pages 2,3,4,6,8,9,10,11,47,64 \\
        --label baseline \\
        --output ../../docs/dm-baseline-and-after/baseline.md

reprocess 完後跑一次：
    uv run python ../../scripts/dump_dm_page_chunks.py \\
        --kb-id 559538a4-d2ac-46e8-8e2c-1d04b599d7e6 \\
        --pages 2,3,4,6,8,9,10,11,47,64 \\
        --label after \\
        --output ../../docs/dm-baseline-and-after/after.md

兩者 diff 即可看 prompt 改造後品質差異。
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.models.chunk_model import ChunkModel
from src.infrastructure.db.models.document_model import DocumentModel
from src.infrastructure.db.models.knowledge_base_model import KnowledgeBaseModel


def _parse_pages(s: str) -> list[int]:
    return sorted({int(p.strip()) for p in s.split(",") if p.strip()})


async def _dump(kb_id: str, pages: list[int], label: str) -> str:
    async with async_session_factory() as session:
        kb = (
            await session.execute(
                select(KnowledgeBaseModel).where(KnowledgeBaseModel.id == kb_id)
            )
        ).scalar_one_or_none()
        if kb is None:
            raise SystemExit(f"KB not found: {kb_id}")

        # 找 parent doc（PDF 上傳的根 doc）
        parent_q = select(DocumentModel).where(
            DocumentModel.kb_id == kb_id,
            DocumentModel.parent_id.is_(None),
            DocumentModel.content_type == "application/pdf",
        )
        parents = (await session.execute(parent_q)).scalars().all()

        # 找指定頁面的 child doc
        child_q = (
            select(DocumentModel)
            .where(
                DocumentModel.kb_id == kb_id,
                DocumentModel.parent_id.is_not(None),
                DocumentModel.page_number.in_(pages),
            )
            .order_by(DocumentModel.page_number, DocumentModel.created_at)
        )
        children = (await session.execute(child_q)).scalars().all()

        # 撈 children 對應的 chunks
        child_ids = [c.id for c in children]
        chunks: list[ChunkModel] = []
        if child_ids:
            chunk_q = (
                select(ChunkModel)
                .where(ChunkModel.document_id.in_(child_ids))
                .order_by(ChunkModel.document_id, ChunkModel.chunk_index)
            )
            chunks = list((await session.execute(chunk_q)).scalars().all())

        chunks_by_doc: dict[str, list[ChunkModel]] = {}
        for c in chunks:
            chunks_by_doc.setdefault(c.document_id, []).append(c)

        children_by_page: dict[int, list[DocumentModel]] = {}
        for c in children:
            children_by_page.setdefault(c.page_number or 0, []).append(c)

    # render markdown
    out: list[str] = []
    out.append(f"# DM page chunks dump — label=`{label}`")
    out.append("")
    out.append(f"- **KB**: `{kb_id}` ({kb.name})")
    out.append(f"- **KB.ocr_mode**: `{kb.ocr_mode}`")
    out.append(f"- **Parent docs**: {len(parents)}（取最舊一份做 reference）")
    if parents:
        p0 = sorted(parents, key=lambda d: d.created_at)[0]
        out.append(f"  - parent_id: `{p0.id}` filename=`{p0.filename}` status=`{p0.status}`")
    out.append(f"- **Pages requested**: {pages}")
    out.append(f"- **Child docs found**: {len(children)}")
    out.append(f"- **Total chunks**: {len(chunks)}")
    out.append(f"- **Dumped at**: {datetime.now(timezone.utc).isoformat()}")
    out.append("")

    for page_no in pages:
        out.append(f"---\n\n## Page {page_no}\n")
        page_children = children_by_page.get(page_no, [])
        if not page_children:
            out.append(f"_(no child doc with page_number={page_no})_\n")
            continue
        for child in page_children:
            child_chunks = chunks_by_doc.get(child.id, [])
            out.append(f"### child doc `{child.id}` — `{child.filename}`")
            out.append("")
            out.append(f"- status: `{child.status}`")
            out.append(f"- chunk_count: `{child.chunk_count}` (actual: {len(child_chunks)})")
            out.append(f"- created_at: {child.created_at.isoformat()}")
            out.append(f"- updated_at: {child.updated_at.isoformat()}")
            out.append("")
            if not child_chunks:
                out.append("_(no chunks — possibly failed processing)_\n")
                continue
            for ch in child_chunks:
                out.append(f"#### chunk #{ch.chunk_index} (id=`{ch.id}`)")
                out.append("")
                out.append("```")
                out.append(ch.content)
                out.append("```")
                out.append("")

    return "\n".join(out)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb-id", required=True)
    ap.add_argument("--pages", required=True, help="逗號分隔，如 '2,3,4,6,8,9,10,11,47,64'")
    ap.add_argument("--label", required=True, help="baseline | after | <自訂>")
    ap.add_argument("--output", required=True, help="輸出 markdown 檔案路徑")
    args = ap.parse_args()

    pages = _parse_pages(args.pages)
    md = await _dump(args.kb_id, pages, args.label)

    out_path = pathlib.Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"wrote {out_path} ({len(md):,} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
