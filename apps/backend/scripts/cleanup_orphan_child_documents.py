"""一次性 cleanup orphan child documents + 它們的 Milvus chunks。

Context（commit 13d4306）：
DeleteDocumentUseCase 之前不 cascade delete child documents。catalog PDF
父刪除後，children 文件 row 與 Milvus 向量都殘留 → RAG 還能搜出來。
Code 層已修，這個 script 處理既有殘留資料。

策略：
1. 找出所有 orphan child documents（parent_id 指向不存在的父 doc）
2. 按 kb_id 分組，逐個 KB 處理
3. Milvus collection ``kb_{kb_id}`` 用 IN list 一次刪所有該 kb 的 orphan
   chunks（reuse MilvusVectorStore.delete + _build_filter_expr 的 IN
   operator 支援）
4. PostgreSQL 用單條 DELETE 把 orphan rows 清掉（FK CASCADE 帶走 chunks）

用法：
    # Dry-run（只列要刪什麼，不動）
    cd apps/backend && uv run python -m scripts.cleanup_orphan_child_documents --dry-run

    # Execute
    uv run python -m scripts.cleanup_orphan_child_documents

    # Dev-vm 透過 IAP SSH 後 set -a && source .env && set +a 再跑
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import defaultdict
from typing import Any

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from sqlalchemy import text  # noqa: E402

from src.infrastructure.db.engine import async_session_factory  # noqa: E402
from src.infrastructure.milvus.milvus_vector_store import (  # noqa: E402
    MilvusVectorStore,
    _safe_collection_name,
)


async def _find_orphans() -> dict[str, list[str]]:
    """Return {kb_id: [orphan_document_id, ...]}."""
    out: dict[str, list[str]] = defaultdict(list)
    async with async_session_factory() as session:
        rows = await session.execute(
            text(
                "SELECT d.id, d.kb_id "
                "FROM documents d "
                "WHERE d.parent_id IS NOT NULL "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM documents p WHERE p.id = d.parent_id"
                ")"
            )
        )
        for doc_id, kb_id in rows:
            out[kb_id].append(doc_id)
    return dict(out)


async def _delete_milvus(
    vs: MilvusVectorStore, kb_id: str, doc_ids: list[str]
) -> str:
    """Delete via IN operator. Skip if collection doesn't exist."""
    collection = _safe_collection_name(f"kb_{kb_id}")
    has = await asyncio.to_thread(vs._client.has_collection, collection)
    if not has:
        return f"collection {collection} not found, skip"
    try:
        await vs.delete(
            collection=collection,
            filters={"document_id": doc_ids},
        )
        return f"milvus deleted {len(doc_ids)} doc_ids from {collection}"
    except Exception as e:
        return f"milvus delete failed: {e}"


async def _delete_postgres(doc_ids: list[str]) -> str:
    """One DELETE pass for all orphans. FK CASCADE handles chunks."""
    async with async_session_factory() as session:
        result = await session.execute(
            text("DELETE FROM documents WHERE id = ANY(:ids)"),
            {"ids": doc_ids},
        )
        await session.commit()
        return f"postgres deleted {result.rowcount} document rows"


async def _find_milvus_only_orphans(
    vs: MilvusVectorStore,
) -> dict[str, list[str]]:
    """Find document_ids that exist in Milvus but NOT in DB documents table.

    這比 _find_orphans 抓的範圍更廣 — 那個只找「DB 中 child 但 parent 不
    存在」，這個找「Milvus 有向量但 DB 完全沒這個 document」。後者通常
    來自舊版 DeleteDocumentUseCase 沒 cascade（pre-cascade-fix 平台
    殘留），或手動操作 DB 漏清向量。
    """
    out: dict[str, list[str]] = defaultdict(list)
    async with async_session_factory() as session:
        rows = await session.execute(
            text("SELECT id, name FROM knowledge_bases")
        )
        kbs = [(r[0], r[1]) for r in rows]

    for kb_id, name in kbs:
        col = _safe_collection_name(f"kb_{kb_id}")
        has = await asyncio.to_thread(vs._client.has_collection, col)
        if not has:
            continue
        try:
            res = await asyncio.to_thread(
                vs._client.query,
                collection_name=col,
                filter="",
                output_fields=["document_id"],
                limit=16384,
            )
        except Exception as e:
            print(f"  {name}: query failed: {e}")
            continue
        milvus_ids = {r["document_id"] for r in res}
        async with async_session_factory() as s2:
            db_rows = await s2.execute(
                text("SELECT id FROM documents WHERE kb_id = :k"),
                {"k": kb_id},
            )
            db_ids = {r[0] for r in db_rows}
        orphan_ids = milvus_ids - db_ids
        if orphan_ids:
            out[kb_id] = list(orphan_ids)
    return dict(out)


async def run(dry_run: bool) -> None:
    print("=== Orphan Documents + Milvus Vectors Cleanup ===")
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")

    # Phase 1: DB-level orphans (children whose parent missing)
    by_kb = await _find_orphans()

    # Phase 2: Milvus-only orphans (vectors whose doc_id missing in DB)
    uri = os.environ.get("MILVUS_URI", "http://localhost:19530")
    token = os.environ.get("MILVUS_TOKEN") or ""
    db_name = os.environ.get("MILVUS_DB_NAME", "default")
    vs = MilvusVectorStore(uri=uri, token=token, db_name=db_name)

    print("\n--- Phase 2: scanning Milvus for orphan vectors ---")
    milvus_orphans = await _find_milvus_only_orphans(vs)

    if not by_kb and not milvus_orphans:
        print("No orphans found anywhere. Nothing to clean.")
        return

    if by_kb:
        total_db = sum(len(ids) for ids in by_kb.values())
        print(f"\nDB-orphans (children with missing parent): {total_db} docs across {len(by_kb)} KBs")
        for kb_id, ids in by_kb.items():
            print(f"  - {kb_id}: {len(ids)} orphans")

    if milvus_orphans:
        total_milvus = sum(len(ids) for ids in milvus_orphans.values())
        print(f"\nMilvus-only orphans (vectors with no DB doc): {total_milvus} doc_ids across {len(milvus_orphans)} KBs")
        for kb_id, ids in milvus_orphans.items():
            print(f"  - {kb_id}: {len(ids)} doc_ids -> sample: {ids[:2]}")

    if dry_run:
        print("\n(dry-run — no changes made. Re-run without --dry-run to apply.)")
        return

    # Phase 1 deletes: DB-orphan children (Milvus + DB)
    if by_kb:
        print("\n--- Phase 1 Milvus deletes (DB-orphans) ---")
        for kb_id, doc_ids in by_kb.items():
            result = await _delete_milvus(vs, kb_id, doc_ids)
            print(f"  {kb_id}: {result}")

        print("\n--- Phase 1 PostgreSQL deletes (DB-orphans) ---")
        all_ids: list[str] = [d for ids in by_kb.values() for d in ids]
        pg_result = await _delete_postgres(all_ids)
        print(f"  {pg_result}")

    # Phase 2 deletes: Milvus-only orphans (no PG row to delete)
    if milvus_orphans:
        print("\n--- Phase 2 Milvus deletes (Milvus-only orphans) ---")
        for kb_id, doc_ids in milvus_orphans.items():
            result = await _delete_milvus(vs, kb_id, doc_ids)
            print(f"  {kb_id}: {result}")

    print("\n=== Cleanup complete ===")


def _entrypoint() -> None:
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run(dry_run))


if __name__ == "__main__":
    _entrypoint()
