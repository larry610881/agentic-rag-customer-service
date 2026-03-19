from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.application.knowledge.create_knowledge_base_use_case import (
    CreateKnowledgeBaseCommand,
    CreateKnowledgeBaseUseCase,
)
from src.application.knowledge.delete_knowledge_base_use_case import (
    DeleteKnowledgeBaseUseCase,
)
from src.application.knowledge.list_all_knowledge_bases_use_case import (
    ListAllKnowledgeBasesUseCase,
)
from src.application.knowledge.list_knowledge_bases_use_case import (
    ListKnowledgeBasesUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant
from src.interfaces.api.schemas.pagination import PaginatedResponse, PaginationQuery

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge-bases"])


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    description: str = ""


class KnowledgeBaseResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str
    document_count: int
    created_at: str
    updated_at: str


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_knowledge_base(
    body: CreateKnowledgeBaseRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: CreateKnowledgeBaseUseCase = Depends(
        Provide[Container.create_knowledge_base_use_case]
    ),
) -> KnowledgeBaseResponse:
    kb = await use_case.execute(
        CreateKnowledgeBaseCommand(
            tenant_id=tenant.tenant_id,
            name=body.name,
            description=body.description,
        )
    )
    return KnowledgeBaseResponse(
        id=kb.id.value,
        tenant_id=kb.tenant_id,
        name=kb.name,
        description=kb.description,
        document_count=kb.document_count,
        created_at=kb.created_at.isoformat(),
        updated_at=kb.updated_at.isoformat(),
    )


@router.get("", response_model=PaginatedResponse[KnowledgeBaseResponse])
@inject
async def list_knowledge_bases(
    tenant_id: str | None = Query(default=None),
    pagination: PaginationQuery = Depends(),
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListKnowledgeBasesUseCase = Depends(
        Provide[Container.list_knowledge_bases_use_case]
    ),
    list_all_use_case: ListAllKnowledgeBasesUseCase = Depends(
        Provide[Container.list_all_knowledge_bases_use_case]
    ),
) -> PaginatedResponse[KnowledgeBaseResponse]:
    limit = pagination.page_size
    offset = (pagination.page - 1) * pagination.page_size
    if tenant.role == "system_admin":
        kbs = await list_all_use_case.execute(
            tenant_id=tenant_id, limit=limit, offset=offset,
        )
        total = await list_all_use_case.count(tenant_id=tenant_id)
    else:
        kbs = await use_case.execute(
            tenant.tenant_id, limit=limit, offset=offset,
        )
        total = await use_case.count(tenant.tenant_id)
    from math import ceil
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[
            KnowledgeBaseResponse(
                id=kb.id.value,
                tenant_id=kb.tenant_id,
                name=kb.name,
                description=kb.description,
                document_count=kb.document_count,
                created_at=kb.created_at.isoformat(),
                updated_at=kb.updated_at.isoformat(),
            )
            for kb in kbs
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_knowledge_base(
    kb_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: DeleteKnowledgeBaseUseCase = Depends(
        Provide[Container.delete_knowledge_base_use_case]
    ),
) -> None:
    try:
        await use_case.execute(kb_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None
