"""父文件 status / quality 聚合 helper.

從 process_document / reprocess_document 兩條 pipeline 抽出共用邏輯：
當子頁全部完成（processed + failed == total）時：
- 父 status: 全部 processed → 'processed'，否則 'failed'
- 父 chunk_count: 子頁加總
- 父 quality: 子頁加權平均

之前兩條 pipeline 各自實作 → reprocess 子頁時父 doc 不會更新（drift bug）
集中於此避免再次發生。
"""

from __future__ import annotations

from src.domain.knowledge.repository import DocumentRepository


async def aggregate_parent_status_if_complete(
    doc_repo: DocumentRepository,
    parent_id: str,
    log,
) -> None:
    """檢查 parent_id 的子頁是否全部完成；若是則更新父 status / quality / chunk_count。

    使用 try/except 包覆所有外呼 — 聚合失敗不應炸 caller pipeline。
    """
    try:
        status_counts = await doc_repo.count_children_by_status(parent_id)
        total = sum(status_counts.values())
        done = status_counts.get("processed", 0)
        failed = status_counts.get("failed", 0)
        if done + failed != total:
            return  # still in flight

        parent_status = "processed" if failed == 0 else "failed"

        # Aggregate chunk counts + quality from all children
        children = await doc_repo.find_children(parent_id)
        total_chunks = sum(c.chunk_count for c in children)

        children_with_chunks = [c for c in children if c.chunk_count > 0]
        if children_with_chunks:
            avg_quality = sum(c.quality_score for c in children_with_chunks) / len(
                children_with_chunks
            )
            avg_chunk_len = sum(
                c.avg_chunk_length for c in children_with_chunks
            ) // len(children_with_chunks)
            valid_min = [
                c.min_chunk_length
                for c in children_with_chunks
                if c.min_chunk_length > 0
            ]
            min_chunk_len = min(valid_min) if valid_min else 0
            max_chunk_len = max(c.max_chunk_length for c in children_with_chunks)

            all_issues: set[str] = set()
            for c in children_with_chunks:
                all_issues.update(c.quality_issues)

            try:
                await doc_repo.update_quality(
                    parent_id,
                    quality_score=round(avg_quality, 3),
                    avg_chunk_length=avg_chunk_len,
                    min_chunk_length=min_chunk_len,
                    max_chunk_length=max_chunk_len,
                    quality_issues=list(all_issues),
                )
            except Exception:
                log.warning("parent.quality_update_failed", exc_info=True)

        await doc_repo.update_status(
            parent_id, parent_status, chunk_count=total_chunks
        )
        log.info(
            "document.parent.aggregated",
            parent_id=parent_id,
            status=parent_status,
            total_chunks=total_chunks,
            children=total,
        )
    except Exception:
        log.warning(
            "document.parent.aggregate_failed", parent_id=parent_id, exc_info=True
        )
