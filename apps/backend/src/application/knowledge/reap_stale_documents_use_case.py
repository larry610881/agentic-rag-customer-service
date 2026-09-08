"""把「卡在等待中卻沒有任何工作在跑」的文件轉成失敗。

為什麼需要這支：`arq_pool.enqueue()` 吞掉所有例外只回 `None`，`confirm-upload`
也不檢查回傳值，所以派工失敗在 UI 上長得跟正常排隊一模一樣 —— 一個轉圈圈的
「等待中」，永遠不會結束。2026-09-08 秋季展批次上傳就出現三筆這種孤兒（前端
429 重試把整個上傳流程從 `request-upload` 重跑，建立了第二列文件，第一列
再也拿不到 `confirm-upload`）。使用者看到的是系統在假裝處理中。

判定「派工遺失」的關鍵在**不能只看時間**：`split_pdf` 會一次生出上百個 child
文件排隊等 OCR，單一 worker `max_jobs=3` 跑完要半小時以上，純看年齡會把合法
排隊中的 child 全部誤殺。所以主要判準是**佇列見底**：

- worker 一撿到工作就會把文件轉 `processing`，因此「文件還是 pending」+
  「arq 佇列長度為 0」= 這份文件的工作根本不存在，可以直接判死。
- 佇列還有積壓時保守處理，只有超過絕對上限（預設 6 小時）才判死，並記 warning。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.domain.knowledge.repository import (
    DocumentRepository,
    ProcessingTaskRepository,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

#: 佇列見底時，pending 超過這個時間即視為派工遺失
DEFAULT_GRACE_MINUTES = 15
#: 佇列仍有積壓時的絕對上限 —— 再深的佇列也不該讓一份文件等這麼久
DEFAULT_HARD_LIMIT_MINUTES = 360
#: 單次 cron 最多處理幾筆，避免一次掃爆
DEFAULT_BATCH_SIZE = 200

ORPHANED_MESSAGE = (
    "派工遺失：文件已建立但處理工作未進入佇列（上傳確認未完成或派工失敗），"
    "非處理中。請重新上傳或點選重新處理。"
)


@dataclass
class ReapResult:
    scanned: int = 0
    failed: int = 0
    skipped_queue_busy: int = 0


class ReapStaleDocumentsUseCase:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        task_repo: ProcessingTaskRepository,
        *,
        grace_minutes: int = DEFAULT_GRACE_MINUTES,
        hard_limit_minutes: int = DEFAULT_HARD_LIMIT_MINUTES,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._doc_repo = doc_repo
        self._task_repo = task_repo
        self._grace = timedelta(minutes=grace_minutes)
        self._hard_limit = timedelta(minutes=hard_limit_minutes)
        self._batch_size = batch_size

    async def execute(self, queue_depth: int) -> ReapResult:
        now = datetime.now(timezone.utc)
        stale = await self._doc_repo.find_stale_pending(
            older_than=now - self._grace, limit=self._batch_size
        )
        result = ReapResult(scanned=len(stale))
        if not stale:
            return result

        # 佇列見底 → pending 的工作不可能存在；佇列有積壓（或 -1 探測失敗）→
        # 保守處理，只殺超過絕對上限的。
        deadline = now - (
            self._grace if queue_depth == 0 else self._hard_limit
        )

        for doc in stale:
            age_ref = doc.updated_at or doc.created_at
            if age_ref and age_ref > deadline:
                result.skipped_queue_busy += 1
                continue

            await self._doc_repo.update_status(doc.id.value, "failed")
            task = await self._task_repo.find_by_document_id(doc.id.value)
            if task is not None:
                await self._task_repo.update_status(
                    task.id.value, "failed", error_message=ORPHANED_MESSAGE
                )
            result.failed += 1
            logger.warning(
                "document.reap.orphaned",
                document_id=doc.id.value,
                kb_id=doc.kb_id,
                tenant_id=doc.tenant_id,
                filename=doc.filename,
                queue_depth=queue_depth,
                age_minutes=round((now - age_ref).total_seconds() / 60)
                if age_ref
                else None,
            )

        if result.skipped_queue_busy:
            logger.info(
                "document.reap.deferred",
                skipped=result.skipped_queue_busy,
                queue_depth=queue_depth,
            )
        return result
