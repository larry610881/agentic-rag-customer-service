"""文件管線的配額預檢入口 — Issue #74（process / reprocess 共用）

用完即擋時：文件狀態 `quota_exhausted`、任務 failed（帶固定文案），不啟動任何
OCR / embedding。預檢 fail-open 由 `QuotaPreflightService` 負責。
"""

from __future__ import annotations

from typing import Any

from src.domain.usage.category import UsageCategory

DOCUMENT_STATUS_QUOTA_EXHAUSTED = "quota_exhausted"


async def quota_blocked_for_document(
    *,
    quota_preflight: Any | None,
    doc_repo: Any,
    task_repo: Any,
    document_id: str,
    tenant_id: str,
    task_id: str,
    log: Any,
) -> bool:
    """回 True 表示已被擋（呼叫端直接 return）。"""
    if quota_preflight is None:
        return False
    decision = await quota_preflight.check(tenant_id, UsageCategory.EMBEDDING.value)
    if decision.allowed:
        return False
    log.warning(
        "document.quota_exhausted",
        tenant_id=tenant_id,
        policy=decision.policy,
        remaining=decision.remaining,
    )
    await doc_repo.update_status(document_id, DOCUMENT_STATUS_QUOTA_EXHAUSTED)
    await task_repo.update_status(task_id, "failed", error_message=decision.message)
    return True
