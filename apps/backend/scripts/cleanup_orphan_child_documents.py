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


async def run(dry_run: bool) -> None:
    print("=== Orphan Child Documents Cleanup ===")
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")

    by_kb = await _find_orphans()
    if not by_kb:
        print("No orphan child documents found. Nothing to clean.")
        return

    total_docs = sum(len(ids) for ids in by_kb.values())
    print(f"\nFound {total_docs} orphan documents across {len(by_kb)} KBs:")
    for kb_id, ids in by_kb.items():
        print(f"  - {kb_id}: {len(ids)} orphans")

    if dry_run:
        print("\n(dry-run — no changes made. Re-run without --dry-run to apply.)")
        return

    # Execute Milvus deletes first (additive — if PG delete fails, we're not
    # left with PG-deleted but Milvus-still-has)
    uri = os.environ.get("MILVUS_URI", "http://localhost:19530")
    token = os.environ.get("MILVUS_TOKEN") or ""
    db_name = os.environ.get("MILVUS_DB_NAME", "default")
    vs = MilvusVectorStore(uri=uri, token=token, db_name=db_name)

    print("\n--- Milvus deletes ---")
    for kb_id, doc_ids in by_kb.items():
        result = await _delete_milvus(vs, kb_id, doc_ids)
        print(f"  {kb_id}: {result}")

    print("\n--- PostgreSQL deletes ---")
    all_ids: list[str] = [d for ids in by_kb.values() for d in ids]
    pg_result = await _delete_postgres(all_ids)
    print(f"  {pg_result}")

    print("\n=== Cleanup complete ===")


def _entrypoint() -> None:
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run(dry_run))


if __name__ == "__main__":
    _entrypoint()
