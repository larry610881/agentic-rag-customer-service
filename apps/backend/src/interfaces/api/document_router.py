from dependency_injector.wiring import Provide, inject
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    UploadFile,
    status,
)
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
from src.application.knowledge.process_document_use_case import (
    ProcessDocumentUseCase,
)
from src.application.knowledge.reprocess_document_use_case import (
    ReprocessDocumentUseCase,
)
from src.application.knowledge.upload_document_use_case import (
    UploadDocumentCommand,
    UploadDocumentUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import (
    EntityNotFoundError,
    UnsupportedFileTypeError,
)
from src.infrastructure.logging.error_handler import safe_background_task
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(
    prefix="/api/v1/knowledge-bases/{kb_id}/documents",
    tags=["documents"],
)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


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
    created_at: str
    updated_at: str


class UploadDocumentResponse(BaseModel):
    document: DocumentResponse
    task_id: str


def _to_response(doc) -> DocumentResponse:
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
        created_at=doc.created_at.isoformat(),
        updated_at=doc.updated_at.isoformat(),
    )


@router.get("", response_model=list[DocumentResponse])
@inject
async def list_documents(
    kb_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListDocumentsUseCase = Depends(
        Provide[Container.list_documents_use_case]
    ),
) -> list[DocumentResponse]:
    documents = await use_case.execute(kb_id)
    return [_to_response(doc) for doc in documents]


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
    process_use_case: ProcessDocumentUseCase = Depends(
        Provide[Container.process_document_use_case]
    ),
) -> UploadDocumentResponse:
    raw_content = await file.read()
    if len(raw_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit",
        )

    content_type = file.content_type or "application/octet-stream"

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

    # Trigger async processing
    background_tasks.add_task(
        safe_background_task,
        process_use_case.execute,
        result.document.id.value,
        result.task.id.value,
        task_name="process_document",
    )

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


class ReprocessRequest(BaseModel):
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    chunk_strategy: str | None = None


@router.post(
    "/{doc_id}/reprocess",
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
) -> dict:
    background_tasks.add_task(
        safe_background_task,
        use_case.execute,
        doc_id,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        chunk_strategy=body.chunk_strategy,
        task_name="reprocess_document",
    )
    return {"status": "accepted", "document_id": doc_id}
