from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.knowledge.get_processing_task_use_case import (
    GetProcessingTaskUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class TaskResponse(BaseModel):
    id: str
    document_id: str
    tenant_id: str
    status: str
    progress: int
    error_message: str
    created_at: str
    updated_at: str


@router.get("/{task_id}", response_model=TaskResponse)
@inject
async def get_task(
    task_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetProcessingTaskUseCase = Depends(
        Provide[Container.get_processing_task_use_case]
    ),
) -> TaskResponse:
    try:
        task = await use_case.execute(task_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None

    if task.tenant_id != tenant.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ProcessingTask not found",
        )

    return TaskResponse(
        id=task.id.value,
        document_id=task.document_id,
        tenant_id=task.tenant_id,
        status=task.status,
        progress=task.progress,
        error_message=task.error_message,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )
