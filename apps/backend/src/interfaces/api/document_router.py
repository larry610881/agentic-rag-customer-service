import asyncio
from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import Response
from pydantic import BaseModel

from src.application.knowledge.delete_document_use_case import (
    DeleteDocumentUseCase,
)
from src.application.knowledge.get_document_chunks_use_case import (
    GetDocumentChunksUseCase,
)
from src.application.knowledge.get_document_quality_stats_use_case import (
    GetDocumentQualityStatsUseCase,
)
from src.application.knowledge.list_documents_use_case import (
    ListDocumentsUseCase,
)
from src.application.knowledge.reprocess_document_use_case import (
    ReprocessDocumentUseCase,
)
from src.application.knowledge.upload_document_use_case import (
    RequestUploadCommand,
    UploadDocumentCommand,
    UploadDocumentUseCase,
)
from src.application.knowledge.view_document_use_case import (
    ViewDocumentUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import (
    EntityNotFoundError,
    UnsupportedFileTypeError,
)
from src.infrastructure.logging.error_handler import safe_background_task
from src.interfaces.api.deps import CurrentTenant, get_current_tenant
from src.interfaces.api.schemas.pagination import PaginatedResponse, PaginationQuery

router = APIRouter(
    prefix="/api/v1/knowledge-bases/{kb_id}/documents",
    tags=["documents"],
)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

# Fallback mapping: browsers often send application/octet-stream for these
_EXT_TO_CONTENT_TYPE: dict[str, str] = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".xml": "text/xml",
    ".html": "text/html",
    ".htm": "text/html",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".rtf": "application/rtf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}


def _resolve_content_type(browser_type: str, filename: str) -> str:
    """Use file extension to resolve content_type when browser sends a generic MIME."""
    if browser_type not in ("application/octet-stream", ""):
        return browser_type
    ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
    return _EXT_TO_CONTENT_TYPE.get(ext, browser_type)


class DocumentResponse(BaseModel):
    id: str
    kb_id: str
    tenant_id: str
    filename: str
    content_type: str
    status: str
    chunk_count: int
    avg_chunk_length: int
    min_chunk_length: int
    max_chunk_length: int
    quality_score: float
    quality_issues: list[str]
    has_file: bool
    task_progress: int | None = None
    created_at: str
    updated_at: str


class UploadDocumentResponse(BaseModel):
    document: DocumentResponse
    task_id: str


def _to_response(doc, task_progress: int | None = None) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id.value,
        kb_id=doc.kb_id,
        tenant_id=doc.tenant_id,
        filename=doc.filename,
        content_type=doc.content_type,
        status=doc.status,
        chunk_count=doc.chunk_count,
        avg_chunk_length=doc.avg_chunk_length,
        min_chunk_length=doc.min_chunk_length,
        max_chunk_length=doc.max_chunk_length,
        quality_score=doc.quality_score,
        quality_issues=doc.quality_issues,
        has_file=bool(doc.storage_path or doc.raw_content),
        task_progress=task_progress,
        created_at=doc.created_at.isoformat(),
        updated_at=doc.updated_at.isoformat(),
    )


@router.get("", response_model=PaginatedResponse[DocumentResponse])
@inject
async def list_documents(
    kb_id: str,
    pagination: PaginationQuery = Depends(),
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListDocumentsUseCase = Depends(
        Provide[Container.list_documents_use_case]
    ),
) -> PaginatedResponse[DocumentResponse]:
    limit = pagination.page_size
    offset = (pagination.page - 1) * pagination.page_size
    documents = await use_case.execute(kb_id, limit=limit, offset=offset)
    total = await use_case.count(kb_id)
    from math import ceil
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0

    # Fetch task progress for processing documents
    progress_map: dict[str, int] = {}
    processing_doc_ids = [
        doc.id.value for doc in documents if doc.status == "processing"
    ]
    if processing_doc_ids:
        from src.infrastructure.db.engine import async_session_factory
        from src.infrastructure.db.models.processing_task_model import (
            ProcessingTaskModel,
        )
        from sqlalchemy import select

        async with async_session_factory() as session:
            stmt = (
                select(
                    ProcessingTaskModel.document_id,
                    ProcessingTaskModel.progress,
                )
                .where(
                    ProcessingTaskModel.document_id.in_(processing_doc_ids),
                    ProcessingTaskModel.status == "processing",
                )
            )
            rows = await session.execute(stmt)
            for row in rows.all():
                progress_map[row[0]] = row[1]

    return PaginatedResponse(
        items=[
            _to_response(doc, progress_map.get(doc.id.value))
            for doc in documents
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


class DocumentQualityStatResponse(BaseModel):
    document_id: str
    filename: str
    quality_score: float
    negative_feedback_count: int


@router.get("/quality-stats", response_model=list[DocumentQualityStatResponse])
@inject
async def get_quality_stats(
    kb_id: str,
    days: int = 30,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetDocumentQualityStatsUseCase = Depends(
        Provide[Container.get_document_quality_stats_use_case]
    ),
) -> list[DocumentQualityStatResponse]:
    stats = await use_case.execute(kb_id, tenant.tenant_id, days=days)
    return [
        DocumentQualityStatResponse(
            document_id=s.document_id,
            filename=s.filename,
            quality_score=s.quality_score,
            negative_feedback_count=s.negative_feedback_count,
        )
        for s in stats
    ]


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_document(
    kb_id: str,
    doc_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: DeleteDocumentUseCase = Depends(
        Provide[Container.delete_document_use_case]
    ),
) -> None:
    try:
        await use_case.execute(doc_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None


@router.post(
    "",
    response_model=UploadDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def upload_document(
    kb_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: UploadDocumentUseCase = Depends(
        Provide[Container.upload_document_use_case]
    ),
) -> UploadDocumentResponse:
    raw_content = await file.read()
    if len(raw_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit",
        )

    content_type = _resolve_content_type(
        file.content_type or "application/octet-stream",
        file.filename or "unnamed",
    )

    try:
        result = await use_case.execute(
            UploadDocumentCommand(
                kb_id=kb_id,
                tenant_id=tenant.tenant_id,
                filename=file.filename or "unnamed",
                content_type=content_type,
                raw_content=raw_content,
            )
        )
    except UnsupportedFileTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=e.message
        ) from None
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None

    from src.infrastructure.queue.arq_pool import enqueue
    await enqueue("process_document", result.document.id.value, result.task.id.value)

    doc = result.document
    return UploadDocumentResponse(
        document=_to_response(doc),
        task_id=result.task.id.value,
    )


class RequestUploadBody(BaseModel):
    filename: str
    content_type: str


class RequestUploadResponse(BaseModel):
    document_id: str
    task_id: str
    upload_url: str
    storage_path: str


@router.post("/request-upload", response_model=RequestUploadResponse)
@inject
async def request_upload(
    kb_id: str,
    body: RequestUploadBody,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: UploadDocumentUseCase = Depends(
        Provide[Container.upload_document_use_case]
    ),
) -> RequestUploadResponse:
    """Request a signed URL for direct GCS upload (bypasses Cloud Run 32MB limit)."""
    try:
        result = await use_case.request_upload(
            RequestUploadCommand(
                kb_id=kb_id,
                tenant_id=tenant.tenant_id,
                filename=body.filename,
                content_type=body.content_type,
            )
        )
    except UnsupportedFileTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=e.message
        ) from None
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None

    if not result.upload_url:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Direct upload not supported with current storage backend",
        )

    return RequestUploadResponse(
        document_id=result.document_id,
        task_id=result.task_id,
        upload_url=result.upload_url,
        storage_path=result.storage_path,
    )


class ConfirmUploadBody(BaseModel):
    document_id: str
    task_id: str


@router.post("/confirm-upload", response_model=UploadDocumentResponse)
@inject
async def confirm_upload(
    kb_id: str,
    body: ConfirmUploadBody,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: UploadDocumentUseCase = Depends(
        Provide[Container.upload_document_use_case]
    ),
) -> UploadDocumentResponse:
    """Confirm direct GCS upload completed, trigger background processing."""
    import logging as _logging
    _log = _logging.getLogger("confirm_upload")

    try:
        result = await use_case.confirm_upload(body.document_id, body.task_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None

    from src.infrastructure.queue.arq_pool import enqueue
    await enqueue("process_document", result.document.id.value, result.task.id.value)

    doc = result.document
    return UploadDocumentResponse(
        document=_to_response(doc),
        task_id=result.task.id.value,
    )


class ChunkPreviewItemResponse(BaseModel):
    id: str
    content: str
    chunk_index: int
    issues: list[str]


class ChunkPreviewListResponse(BaseModel):
    chunks: list[ChunkPreviewItemResponse]
    total: int


@router.get("/{doc_id}/chunks", response_model=ChunkPreviewListResponse)
@inject
async def get_document_chunks(
    kb_id: str,
    doc_id: str,
    limit: int = 20,
    offset: int = 0,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetDocumentChunksUseCase = Depends(
        Provide[Container.get_document_chunks_use_case]
    ),
) -> ChunkPreviewListResponse:
    result = await use_case.execute(doc_id, limit=limit, offset=offset)
    return ChunkPreviewListResponse(
        chunks=[
            ChunkPreviewItemResponse(
                id=c.id,
                content=c.content,
                chunk_index=c.chunk_index,
                issues=c.issues,
            )
            for c in result.chunks
        ],
        total=result.total,
    )


@router.get("/{doc_id}/view")
@inject
async def view_document(
    kb_id: str,
    doc_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ViewDocumentUseCase = Depends(
        Provide[Container.view_document_use_case]
    ),
) -> Response:
    try:
        result = await use_case.execute(doc_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from None

    return Response(
        content=result.content,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{result.filename}"'
        },
    )


@router.get("/{doc_id}/preview-url")
@inject
async def get_document_preview_url(
    kb_id: str,
    doc_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    doc_repo: Any = Depends(Provide[Container.document_repository]),
    file_storage: Any = Depends(
        Provide[Container.document_file_storage_service]
    ),
) -> dict:
    """Return a preview URL for the document.

    GCS: returns a signed URL (direct browser access).
    Local: returns null (frontend should fallback to /view endpoint).
    """
    from src.config import settings

    doc = await doc_repo.find_by_id(doc_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found",
        )

    preview_url = None
    if doc.storage_path and hasattr(file_storage, "get_preview_url"):
        expiry = settings.gcs_signed_url_expiry
        preview_url = await file_storage.get_preview_url(
            doc.storage_path, expiry_seconds=expiry,
        )

    return {
        "preview_url": preview_url,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "storage_backend": settings.storage_backend,
    }


class BatchDocIdsRequest(BaseModel):
    doc_ids: list[str]


class BatchFailedItem(BaseModel):
    id: str
    error: str


class BatchDeleteResponse(BaseModel):
    succeeded: list[str]
    failed: list[BatchFailedItem]


class BatchReprocessTaskItem(BaseModel):
    document_id: str
    task_id: str


class BatchReprocessResponse(BaseModel):
    tasks: list[BatchReprocessTaskItem]
    failed: list[BatchFailedItem]


@router.post("/batch-delete", response_model=BatchDeleteResponse)
@inject
async def batch_delete_documents(
    kb_id: str,
    body: BatchDocIdsRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: DeleteDocumentUseCase = Depends(
        Provide[Container.delete_document_use_case]
    ),
) -> BatchDeleteResponse:
    succeeded: list[str] = []
    failed: list[BatchFailedItem] = []
    for doc_id in body.doc_ids:
        try:
            await use_case.execute(doc_id)
            succeeded.append(doc_id)
        except EntityNotFoundError:
            failed.append(BatchFailedItem(id=doc_id, error="Document not found"))
        except Exception as e:
            failed.append(BatchFailedItem(id=doc_id, error=str(e)))
    return BatchDeleteResponse(succeeded=succeeded, failed=failed)


@router.post(
    "/batch-reprocess",
    response_model=BatchReprocessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@inject
async def batch_reprocess_documents(
    kb_id: str,
    body: BatchDocIdsRequest,
    background_tasks: BackgroundTasks,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ReprocessDocumentUseCase = Depends(
        Provide[Container.reprocess_document_use_case]
    ),
) -> BatchReprocessResponse:
    tasks: list[BatchReprocessTaskItem] = []
    failed: list[BatchFailedItem] = []
    for doc_id in body.doc_ids:
        try:
            task = await use_case.begin_reprocess(doc_id, tenant.tenant_id)

            async def _reprocess(d_id: str, t_id: str) -> None:
                uc = Container.reprocess_document_use_case()
                await uc.execute(d_id, t_id)

            background_tasks.add_task(
                safe_background_task,
                _reprocess,
                doc_id,
                task.id.value,
                task_name="reprocess_document",
                tenant_id=tenant.tenant_id,
            )
            tasks.append(
                BatchReprocessTaskItem(document_id=doc_id, task_id=task.id.value)
            )
        except Exception as e:
            failed.append(BatchFailedItem(id=doc_id, error=str(e)))
    return BatchReprocessResponse(tasks=tasks, failed=failed)


class ReprocessRequest(BaseModel):
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    chunk_strategy: str | None = None


class ReprocessDocumentResponse(BaseModel):
    status: str
    document_id: str
    task_id: str


@router.post(
    "/{doc_id}/reprocess",
    response_model=ReprocessDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@inject
async def reprocess_document(
    kb_id: str,
    doc_id: str,
    body: ReprocessRequest,
    background_tasks: BackgroundTasks,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ReprocessDocumentUseCase = Depends(
        Provide[Container.reprocess_document_use_case]
    ),
) -> ReprocessDocumentResponse:
    task = await use_case.begin_reprocess(doc_id, tenant.tenant_id)

    async def _reprocess(
        d_id: str,
        t_id: str,
        chunk_size: int | None,
        chunk_overlap: int | None,
        chunk_strategy: str | None,
    ) -> None:
        uc = Container.reprocess_document_use_case()
        await uc.execute(
            d_id, t_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunk_strategy=chunk_strategy,
        )

    background_tasks.add_task(
        safe_background_task,
        _reprocess,
        doc_id,
        task.id.value,
        body.chunk_size,
        body.chunk_overlap,
        body.chunk_strategy,
        task_name="reprocess_document",
        tenant_id=tenant.tenant_id,
    )
    return ReprocessDocumentResponse(
        status="accepted", document_id=doc_id, task_id=task.id.value
    )
