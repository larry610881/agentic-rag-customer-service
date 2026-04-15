"""Bot Worker CRUD API"""

from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.bot.worker_use_cases import (
    CreateWorkerCommand,
    CreateWorkerUseCase,
    DeleteWorkerUseCase,
    ListWorkersUseCase,
    UpdateWorkerCommand,
    UpdateWorkerUseCase,
)
from src.container import Container

router = APIRouter(
    prefix="/api/v1/bots/{bot_id}/workers", tags=["bot-workers"]
)


# --- Schemas ---


class CreateWorkerRequest(BaseModel):
    name: str
    description: str = ""
    worker_prompt: str = ""
    llm_provider: str | None = None
    llm_model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 1024
    max_tool_calls: int = 5
    enabled_mcp_ids: list[str] = []
    knowledge_base_ids: list[str] = []
    sort_order: int = 0


class UpdateWorkerRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    worker_prompt: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    max_tool_calls: int | None = None
    enabled_mcp_ids: list[str] | None = None
    knowledge_base_ids: list[str] | None = None
    sort_order: int | None = None


class WorkerResponse(BaseModel):
    id: str
    bot_id: str
    name: str
    description: str
    worker_prompt: str
    llm_provider: str | None
    llm_model: str | None
    temperature: float
    max_tokens: int
    max_tool_calls: int
    enabled_mcp_ids: list[str]
    knowledge_base_ids: list[str]
    sort_order: int
    created_at: str
    updated_at: str


def _to_response(w: Any) -> WorkerResponse:
    return WorkerResponse(
        id=w.id,
        bot_id=w.bot_id,
        name=w.name,
        description=w.description,
        worker_prompt=w.worker_prompt,
        llm_provider=w.llm_provider,
        llm_model=w.llm_model,
        temperature=w.temperature,
        max_tokens=w.max_tokens,
        max_tool_calls=w.max_tool_calls,
        enabled_mcp_ids=w.enabled_mcp_ids,
        knowledge_base_ids=w.knowledge_base_ids,
        sort_order=w.sort_order,
        created_at=w.created_at.isoformat(),
        updated_at=w.updated_at.isoformat(),
    )


# --- Endpoints ---


@router.get("", response_model=list[WorkerResponse])
@inject
async def list_workers(
    bot_id: str,
    use_case: ListWorkersUseCase = Depends(
        Provide[Container.list_workers_use_case]
    ),
) -> list[WorkerResponse]:
    workers = await use_case.execute(bot_id)
    return [_to_response(w) for w in workers]


@router.post(
    "",
    response_model=WorkerResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_worker(
    bot_id: str,
    body: CreateWorkerRequest,
    use_case: CreateWorkerUseCase = Depends(
        Provide[Container.create_worker_use_case]
    ),
) -> WorkerResponse:
    worker = await use_case.execute(
        CreateWorkerCommand(
            bot_id=bot_id,
            name=body.name,
            description=body.description,
            worker_prompt=body.worker_prompt,
            llm_provider=body.llm_provider,
            llm_model=body.llm_model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            max_tool_calls=body.max_tool_calls,
            enabled_mcp_ids=body.enabled_mcp_ids,
            knowledge_base_ids=body.knowledge_base_ids,
            sort_order=body.sort_order,
        )
    )
    return _to_response(worker)


@router.put("/{worker_id}", response_model=WorkerResponse)
@inject
async def update_worker(
    bot_id: str,
    worker_id: str,
    body: UpdateWorkerRequest,
    use_case: UpdateWorkerUseCase = Depends(
        Provide[Container.update_worker_use_case]
    ),
) -> WorkerResponse:
    worker = await use_case.execute(
        UpdateWorkerCommand(
            worker_id=worker_id,
            name=body.name,
            description=body.description,
            worker_prompt=body.worker_prompt,
            llm_provider=body.llm_provider,
            llm_model=body.llm_model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            max_tool_calls=body.max_tool_calls,
            enabled_mcp_ids=body.enabled_mcp_ids,
            knowledge_base_ids=body.knowledge_base_ids,
            sort_order=body.sort_order,
        )
    )
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker '{worker_id}' not found",
        )
    return _to_response(worker)


@router.delete(
    "/{worker_id}", status_code=status.HTTP_204_NO_CONTENT
)
@inject
async def delete_worker(
    bot_id: str,
    worker_id: str,
    use_case: DeleteWorkerUseCase = Depends(
        Provide[Container.delete_worker_use_case]
    ),
) -> None:
    await use_case.execute(worker_id)
