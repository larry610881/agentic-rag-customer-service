"""Bulk Ingest use case (Issue #44 — External Producer Integration).

Accepts a list of text documents from an external producer (each with
``content`` + ``filename`` + ``metadata``) and routes each through the
existing single-document upload + arq ``process_document`` pipeline.
Per-item failures are collected into a partial response so a single bad
record does not abort the whole batch.

When an item carries ``metadata.source`` and ``metadata.source_id``, the
use case dedups by issuing ``DELETE /by-source`` for that pair before
creating the new document — letting the producer treat the endpoint as
an idempotent upsert keyed by (source, source_id).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from src.application.knowledge.delete_documents_by_source_use_case import (
    DeleteDocumentsBySourceCommand,
    DeleteDocumentsBySourceUseCase,
)
from src.application.knowledge.upload_document_use_case import (
    UploadDocumentCommand,
    UploadDocumentUseCase,
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
        delete_by_source_use_case: DeleteDocumentsBySourceUseCase,
    ) -> None:
        self._upload = upload_use_case
        self._delete_by_source = delete_by_source_use_case

    async def execute(self, command: BulkIngestCommand) -> BulkIngestResult:
        results: list[BulkIngestResultItem] = []
        indexed = 0
        failed = 0

        for item in command.documents:
            result = await self._ingest_one(command, item)
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
    ) -> BulkIngestResultItem:
        if not item.content or not item.content.strip():
            return BulkIngestResultItem(
                filename=item.filename,
                status="failed",
                error="content_empty",
            )

        source = str(item.metadata.get("source", "") or "")
        source_id = str(item.metadata.get("source_id", "") or "")

        # Auto-dedup: if both source/source_id are provided, sweep prior
        # Milvus chunks for that key so the new ingest fully replaces the
        # old (idempotent upsert semantics).
        if source and source_id:
            try:
                await self._delete_by_source.execute(
                    DeleteDocumentsBySourceCommand(
                        kb_id=command.kb_id,
                        tenant_id=command.tenant_id,
                        source=source,
                        source_ids=[source_id],
                    )
                )
            except EntityNotFoundError as e:
                # KB ownership validation already failed — fail this item
                # with the underlying message so the caller knows their
                # tenant can't write here.
                return BulkIngestResultItem(
                    filename=item.filename,
                    status="failed",
                    error=str(e.message),
                )
            except Exception as e:  # noqa: BLE001
                # Best-effort dedup: do not block ingest on Milvus delete
                # transient failures — log and continue.
                logger.warning(
                    "bulk_ingest.dedup.skipped",
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
