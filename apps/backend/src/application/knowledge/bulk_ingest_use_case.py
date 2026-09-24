"""Bulk Ingest use case (Issue #44 — External Producer Integration).

Accepts a list of text documents from an external producer (each with
``content`` + ``filename`` + ``metadata``) and routes each through the
existing single-document upload + arq ``process_document`` pipeline.
Per-item failures are collected into a partial response so a single bad
record does not abort the whole batch.

When an item carries ``metadata.source`` and ``metadata.source_id``, the
endpoint is an idempotent upsert keyed by (source, source_id): the new
document is uploaded first, then every older top-level document with the same
key is deleted through ``DeleteDocumentUseCase`` (vectors by ``document_id``
with a created_at watermark, plus the PG rows and stored files).

#469963：舊做法先發以 {tenant_id, source, source_id} 過濾的 vector.delete 事件再上傳。
事件在下一次 drain 才套用，新文件若先處理完，它的 chunks 帶同樣的 source/source_id，
會被一起刪掉；舊的 PG 文件紀錄也從未刪除。改為以文件 id 刪除後兩者都不再發生。
順序改為先上傳再刪舊：上傳失敗時舊版仍在，不會兩頭落空。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from src.application.knowledge._admin_kb_check import ensure_kb_accessible
from src.application.knowledge.delete_document_use_case import DeleteDocumentUseCase
from src.application.knowledge.upload_document_use_case import (
    UploadDocumentCommand,
    UploadDocumentUseCase,
)
from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.shared.exceptions import (
    EntityNotFoundError,
    UnsupportedFileTypeError,
)

logger = structlog.get_logger(__name__)

MAX_BULK_DOCUMENTS = 100


@dataclass(frozen=True)
class BulkIngestItem:
    content: str
    filename: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class BulkIngestCommand:
    kb_id: str
    tenant_id: str
    documents: list[BulkIngestItem]


@dataclass
class BulkIngestResultItem:
    filename: str
    status: str  # "accepted" | "failed"
    document_id: str | None = None
    task_id: str | None = None
    error: str | None = None


@dataclass
class BulkIngestResult:
    indexed: int
    failed: int
    results: list[BulkIngestResultItem]


class BulkIngestUseCase:
    def __init__(
        self,
        upload_use_case: UploadDocumentUseCase,
        delete_document_use_case: DeleteDocumentUseCase,
        kb_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
    ) -> None:
        self._upload = upload_use_case
        self._delete_document = delete_document_use_case
        self._kb_repo = kb_repository
        self._doc_repo = document_repository

    async def execute(self, command: BulkIngestCommand) -> BulkIngestResult:
        results: list[BulkIngestResultItem] = []
        indexed = 0
        failed = 0

        # KB 歸屬一次驗完；effective tenant 用於去重查詢（system_admin 代操作時
        # 是 KB 真正的 owner）。不可存取 → 每筆都失敗、訊息相同（與逐筆驗證時一致）。
        try:
            _, effective_tenant_id = await ensure_kb_accessible(
                self._kb_repo, command.kb_id, command.tenant_id
            )
        except EntityNotFoundError as e:
            results = [
                BulkIngestResultItem(
                    filename=item.filename, status="failed", error=str(e.message)
                )
                for item in command.documents
            ]
            return BulkIngestResult(indexed=0, failed=len(results), results=results)

        for item in command.documents:
            result = await self._ingest_one(command, item, effective_tenant_id)
            results.append(result)
            if result.status == "accepted":
                indexed += 1
            else:
                failed += 1

        logger.info(
            "kb.documents.bulk_ingest",
            kb_id=command.kb_id,
            tenant_id=command.tenant_id,
            total=len(command.documents),
            indexed=indexed,
            failed=failed,
        )
        return BulkIngestResult(indexed=indexed, failed=failed, results=results)

    async def _ingest_one(
        self,
        command: BulkIngestCommand,
        item: BulkIngestItem,
        effective_tenant_id: str,
    ) -> BulkIngestResultItem:
        if not item.content or not item.content.strip():
            return BulkIngestResultItem(
                filename=item.filename,
                status="failed",
                error="content_empty",
            )

        source = str(item.metadata.get("source", "") or "")
        source_id = str(item.metadata.get("source_id", "") or "")

        # 去重對象在上傳前先查好，新文件不會被算進去。
        old_doc_ids: list[str] = []
        if source and source_id:
            try:
                old_doc_ids = await self._doc_repo.find_top_level_ids_by_source(
                    command.kb_id, effective_tenant_id, source, source_id
                )
            except Exception as e:  # noqa: BLE001
                # best-effort：查不到舊版就只上傳新版，不擋 ingest
                logger.warning(
                    "bulk_ingest.dedup.lookup_failed",
                    filename=item.filename,
                    source=source,
                    source_id=source_id,
                    error=str(e),
                )

        try:
            upload_result = await self._upload.execute(
                UploadDocumentCommand(
                    kb_id=command.kb_id,
                    tenant_id=command.tenant_id,
                    filename=item.filename,
                    content_type="text/plain",
                    raw_content=item.content.encode("utf-8"),
                    source=source,
                    source_id=source_id,
                )
            )
        except UnsupportedFileTypeError as e:
            return BulkIngestResultItem(
                filename=item.filename,
                status="failed",
                error=e.message,
            )
        except EntityNotFoundError as e:
            return BulkIngestResultItem(
                filename=item.filename,
                status="failed",
                error=e.message,
            )
        except Exception as e:  # noqa: BLE001
            return BulkIngestResultItem(
                filename=item.filename,
                status="failed",
                error=f"upload_failed: {e}",
            )

        await self._delete_old_versions(item, old_doc_ids, command.kb_id)

        # Enqueue arq processing — same path as the single-file POST.
        try:
            from src.infrastructure.queue.arq_pool import enqueue
            await enqueue(
                "process_document",
                upload_result.document.id.value,
                upload_result.task.id.value,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "bulk_ingest.enqueue.failed",
                filename=item.filename,
                document_id=upload_result.document.id.value,
                error=str(e),
            )

        return BulkIngestResultItem(
            filename=item.filename,
            status="accepted",
            document_id=upload_result.document.id.value,
            task_id=upload_result.task.id.value,
        )

    async def _delete_old_versions(
        self, item: BulkIngestItem, doc_ids: list[str], kb_id: str
    ) -> None:
        """新版已上傳成功後刪舊版：走單筆刪除路徑（document_id filter + 時間截點，
        連同 PG 紀錄與檔案）。best-effort：失敗只記 log，不影響新版的 accepted。"""
        for doc_id in doc_ids:
            try:
                await self._delete_document.execute(doc_id, kb_id=kb_id)
            except EntityNotFoundError:
                pass  # 已被並行的請求刪掉，目標達成
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "bulk_ingest.dedup.delete_failed",
                    filename=item.filename,
                    document_id=doc_id,
                    error=str(e),
                )
