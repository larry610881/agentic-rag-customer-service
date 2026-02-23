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

from src.application.knowledge.process_document_use_case import (
    ProcessDocumentUseCase,
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
    created_at: str
    updated_at: str


class UploadDocumentResponse(BaseModel):
    document: DocumentResponse
    task_id: str


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
        process_use_case.execute,
        result.document.id.value,
        result.task.id.value,
    )

    doc = result.document
    return UploadDocumentResponse(
        document=DocumentResponse(
            id=doc.id.value,
            kb_id=doc.kb_id,
            tenant_id=doc.tenant_id,
            filename=doc.filename,
            content_type=doc.content_type,
            status=doc.status,
            chunk_count=doc.chunk_count,
            created_at=doc.created_at.isoformat(),
            updated_at=doc.updated_at.isoformat(),
        ),
        task_id=result.task.id.value,
    )
