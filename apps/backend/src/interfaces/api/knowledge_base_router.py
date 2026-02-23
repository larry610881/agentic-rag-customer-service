from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from src.application.knowledge.create_knowledge_base_use_case import (
    CreateKnowledgeBaseCommand,
    CreateKnowledgeBaseUseCase,
)
from src.application.knowledge.list_knowledge_bases_use_case import (
    ListKnowledgeBasesUseCase,
)
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge-bases"])


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    description: str = ""


class KnowledgeBaseResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str
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
        created_at=kb.created_at.isoformat(),
        updated_at=kb.updated_at.isoformat(),
    )


@router.get("", response_model=list[KnowledgeBaseResponse])
@inject
async def list_knowledge_bases(
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListKnowledgeBasesUseCase = Depends(
        Provide[Container.list_knowledge_bases_use_case]
    ),
) -> list[KnowledgeBaseResponse]:
    kbs = await use_case.execute(tenant.tenant_id)
    return [
        KnowledgeBaseResponse(
            id=kb.id.value,
            tenant_id=kb.tenant_id,
            name=kb.name,
            description=kb.description,
            created_at=kb.created_at.isoformat(),
            updated_at=kb.updated_at.isoformat(),
        )
        for kb in kbs
    ]
