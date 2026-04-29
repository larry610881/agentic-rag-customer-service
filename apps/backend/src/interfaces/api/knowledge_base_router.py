from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.knowledge.create_knowledge_base_use_case import (
    CreateKnowledgeBaseCommand,
    CreateKnowledgeBaseUseCase,
)
from src.application.knowledge.delete_knowledge_base_use_case import (
    DeleteKnowledgeBaseUseCase,
)
from src.application.knowledge.list_knowledge_bases_use_case import (
    ListKnowledgeBasesUseCase,
)
from src.application.knowledge.update_knowledge_base_use_case import (
    UpdateKnowledgeBaseCommand,
    UpdateKnowledgeBaseUseCase,
)
from src.container import Container
from src.domain.knowledge.repository import (
    ChunkCategoryRepository,
    KnowledgeBaseRepository,
)
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant
from src.interfaces.api.schemas.pagination import PaginatedResponse, PaginationQuery

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge-bases"])


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    description: str = ""
    ocr_mode: str = "general"
    ocr_model: str = ""
    context_model: str = ""
    classification_model: str = ""


class UpdateKnowledgeBaseRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    ocr_mode: str | None = None
    ocr_model: str | None = None
    context_model: str | None = None
    classification_model: str | None = None


class KnowledgeBaseResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str
    ocr_mode: str
    ocr_model: str = ""
    context_model: str = ""
    classification_model: str = ""
    document_count: int
    created_at: str
    updated_at: str


def _kb_to_response(kb) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=kb.id.value,
        tenant_id=kb.tenant_id,
        name=kb.name,
        description=kb.description,
        ocr_mode=kb.ocr_mode,
        ocr_model=kb.ocr_model,
        context_model=kb.context_model,
        classification_model=kb.classification_model,
        document_count=kb.document_count,
        created_at=kb.created_at.isoformat(),
        updated_at=kb.updated_at.isoformat(),
    )


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
            ocr_mode=body.ocr_mode,
            ocr_model=body.ocr_model,
            context_model=body.context_model,
            classification_model=body.classification_model,
        )
    )
    return _kb_to_response(kb)


@router.get("", response_model=PaginatedResponse[KnowledgeBaseResponse])
@inject
async def list_knowledge_bases(
    pagination: PaginationQuery = Depends(),
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListKnowledgeBasesUseCase = Depends(
        Provide[Container.list_knowledge_bases_use_case]
    ),
) -> PaginatedResponse[KnowledgeBaseResponse]:
    """租戶視角列表；system_admin 在此看到的是 SYSTEM_TENANT 的 KB。
    跨租戶總覽請改呼叫 /api/v1/admin/knowledge-bases（見 S-Gov.3）。"""
    limit = pagination.page_size
    offset = (pagination.page - 1) * pagination.page_size
    kbs = await use_case.execute(
        tenant.tenant_id, limit=limit, offset=offset,
    )
    total = await use_case.count(tenant.tenant_id)
    from math import ceil
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[_kb_to_response(kb) for kb in kbs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
@inject
async def get_knowledge_base(
    kb_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    kb_repo: KnowledgeBaseRepository = Depends(
        Provide[Container.kb_repository]
    ),
) -> KnowledgeBaseResponse:
    """單一 KB 詳情（KB Studio 設定 tab 用）。

    system_admin (SYSTEM_TENANT_ID) 可看任意租戶 KB；
    一般 tenant 只能看自己的（找不到 → 404 防枚舉）。
    """
    from src.application.knowledge._admin_kb_check import ensure_kb_accessible
    try:
        kb, _ = await ensure_kb_accessible(kb_repo, kb_id, tenant.tenant_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None
    return _kb_to_response(kb)


@router.patch("/{kb_id}", response_model=KnowledgeBaseResponse)
@inject
async def update_knowledge_base(
    kb_id: str,
    body: UpdateKnowledgeBaseRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    update_use_case: UpdateKnowledgeBaseUseCase = Depends(
        Provide[Container.update_knowledge_base_use_case]
    ),
    kb_repo: KnowledgeBaseRepository = Depends(
        Provide[Container.kb_repository]
    ),
) -> KnowledgeBaseResponse:
    try:
        await update_use_case.execute(
            UpdateKnowledgeBaseCommand(
                kb_id=kb_id,
                name=body.name,
                description=body.description,
                ocr_mode=body.ocr_mode,
                ocr_model=body.ocr_model,
                context_model=body.context_model,
                classification_model=body.classification_model,
                )
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None
    kb = await kb_repo.find_by_id(kb_id)
    return _kb_to_response(kb)


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


# --- Category endpoints ---


class CategoryResponse(BaseModel):
    id: str
    kb_id: str
    name: str
    description: str | None = None
    chunk_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class UpdateCategoryRequest(BaseModel):
    name: str


@router.post("/{kb_id}/classify", status_code=status.HTTP_202_ACCEPTED)
@inject
async def classify_knowledge_base(
    kb_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
) -> dict:
    """Trigger async classification job for a KB."""
    from src.infrastructure.queue.arq_pool import enqueue

    await enqueue("classify_kb", kb_id, tenant.tenant_id)
    return {"status": "accepted", "message": "分類任務已排入佇列"}


@router.get("/{kb_id}/categories", response_model=list[CategoryResponse])
@inject
async def list_categories(
    kb_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    cat_repo: ChunkCategoryRepository = Depends(
        Provide[Container.chunk_category_repository]
    ),
) -> list[CategoryResponse]:
    categories = await cat_repo.find_by_kb(kb_id)
    return [
        CategoryResponse(
            id=c.id,
            kb_id=c.kb_id,
            name=c.name,
            description=c.description,
            chunk_count=c.chunk_count,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
        for c in categories
    ]


@router.patch("/{kb_id}/categories/{cat_id}", response_model=CategoryResponse)
@inject
async def update_category(
    kb_id: str,
    cat_id: str,
    body: UpdateCategoryRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    cat_repo: ChunkCategoryRepository = Depends(
        Provide[Container.chunk_category_repository]
    ),
) -> CategoryResponse:
    cat = await cat_repo.find_by_id(cat_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="分類不存在")
    await cat_repo.update_name(cat_id, body.name)
    cat = await cat_repo.find_by_id(cat_id)
    return CategoryResponse(
        id=cat.id,
        kb_id=cat.kb_id,
        name=cat.name,
        description=cat.description,
        chunk_count=cat.chunk_count,
        created_at=cat.created_at.isoformat(),
        updated_at=cat.updated_at.isoformat(),
    )


class CategoryChunkItemResponse(BaseModel):
    id: str
    content: str
    context_text: str = ""
    chunk_index: int
    cohesion_score: float


class CategoryChunksResponse(BaseModel):
    category_id: str
    category_name: str
    chunk_count: int
    chunks: list[CategoryChunkItemResponse]


@router.get("/{kb_id}/categories/{cat_id}/chunks", response_model=CategoryChunksResponse)
@inject
async def get_category_chunks(
    kb_id: str,
    cat_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: "GetCategoryChunksUseCase" = Depends(
        Provide[Container.get_category_chunks_use_case]
    ),
) -> CategoryChunksResponse:
    result = await use_case.execute(kb_id, cat_id)
    if result is None:
        raise HTTPException(status_code=404, detail="分類不存在")
    return CategoryChunksResponse(
        category_id=result.category_id,
        category_name=result.category_name,
        chunk_count=result.chunk_count,
        chunks=[
            CategoryChunkItemResponse(
                id=c.id,
                content=c.content,
                context_text=c.context_text,
                chunk_index=c.chunk_index,
                cohesion_score=c.cohesion_score,
            )
            for c in result.chunks
        ],
    )


# ---------- S-KB-Studio.1: Category CRUD + 批次指派 ----------


class CreateCategoryRequest(BaseModel):
    name: str
    description: str | None = None


class AssignChunksRequest(BaseModel):
    chunk_ids: list[str]


@router.post(
    "/{kb_id}/categories",
    response_model=CategoryResponse,
    status_code=201,
)
@inject
async def create_category(
    kb_id: str,
    body: CreateCategoryRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case=Depends(Provide[Container.create_category_use_case]),
) -> CategoryResponse:
    from src.application.chunk_category.create_category_use_case import (
        CreateCategoryCommand,
    )
    from src.domain.shared.exceptions import EntityNotFoundError
    try:
        cat = await use_case.execute(
            CreateCategoryCommand(
                kb_id=kb_id,
                tenant_id=tenant.tenant_id,
                name=body.name,
                description=body.description,
                actor=tenant.user_id or tenant.tenant_id or "",
            )
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail="kb not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return CategoryResponse(
        id=cat.id,
        kb_id=cat.kb_id,
        name=cat.name,
        description=cat.description,
        chunk_count=cat.chunk_count,
        created_at=cat.created_at.isoformat() if cat.created_at else None,
        updated_at=cat.updated_at.isoformat() if cat.updated_at else None,
    )


@router.delete(
    "/{kb_id}/categories/{cat_id}", status_code=204
)
@inject
async def delete_category(
    kb_id: str,
    cat_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case=Depends(Provide[Container.delete_category_use_case]),
) -> None:
    from src.application.chunk_category.delete_category_use_case import (
        DeleteCategoryCommand,
    )
    from src.domain.shared.exceptions import EntityNotFoundError
    try:
        await use_case.execute(
            DeleteCategoryCommand(
                kb_id=kb_id,
                category_id=cat_id,
                tenant_id=tenant.tenant_id,
                actor=tenant.user_id or tenant.tenant_id or "",
            )
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail="not found")


@router.post("/{kb_id}/categories/{cat_id}/assign-chunks")
@inject
async def assign_chunks(
    kb_id: str,
    cat_id: str,
    body: AssignChunksRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case=Depends(Provide[Container.assign_chunks_use_case]),
) -> dict:
    from src.application.chunk_category.assign_chunks_use_case import (
        AssignChunksCommand,
    )
    from src.domain.shared.exceptions import EntityNotFoundError
    try:
        count = await use_case.execute(
            AssignChunksCommand(
                kb_id=kb_id,
                category_id=cat_id,
                tenant_id=tenant.tenant_id,
                chunk_ids=body.chunk_ids,
                actor=tenant.user_id or tenant.tenant_id or "",
            )
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    return {"status": "ok", "assigned_count": count}
