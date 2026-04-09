"""Wiki Knowledge Mode API — 編譯觸發 + 狀態查詢。

Endpoints:
  POST /api/v1/bots/{bot_id}/wiki/compile  — 觸發背景編譯
  GET  /api/v1/bots/{bot_id}/wiki/status   — 查詢編譯進度與統計

編譯是 long-running task：
- 透過 FastAPI BackgroundTasks + safe_background_task() wrapper
- 內部用 independent_session_scope() 建立獨立 DB session（避免 pool leak）
- Lazy resolve：background task 必須從 Container 拿新 use case
  （不能用 request-scoped Depends 注入的實例）
"""

from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.wiki.compile_wiki_use_case import (
    CompileWikiCommand,
)
from src.application.wiki.get_wiki_status_use_case import (
    GetWikiStatusUseCase,
)
from src.container import Container
from src.domain.bot.repository import BotRepository
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError
from src.infrastructure.logging.error_handler import safe_background_task
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(prefix="/api/v1/bots", tags=["wiki"])


class CompileWikiResponse(BaseModel):
    bot_id: str
    status: str  # "accepted" — 背景處理中
    message: str


class WikiStatusResponse(BaseModel):
    wiki_graph_id: str
    bot_id: str
    kb_id: str
    status: str  # pending | compiling | ready | stale | failed
    node_count: int
    edge_count: int
    cluster_count: int
    doc_count: int
    compiled_at: str | None
    token_usage: dict | None = None
    errors: list[str] | None = None


@router.post(
    "/{bot_id}/wiki/compile",
    response_model=CompileWikiResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@inject
async def compile_wiki(
    bot_id: str,
    background_tasks: BackgroundTasks,
    tenant: CurrentTenant = Depends(get_current_tenant),
    bot_repository: BotRepository = Depends(
        Provide[Container.bot_repository]
    ),
) -> CompileWikiResponse:
    """觸發 Wiki 編譯背景任務。

    Router 層做 early validation（bot 存在、屬於 tenant、有 KB 綁定），
    確保 API 能回 400/404。實際編譯透過 lazy resolve + 獨立 session 執行。
    """
    bot = await bot_repository.find_by_id(bot_id)
    if bot is None or bot.tenant_id != tenant.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot '{bot_id}' not found",
        )
    if not bot.knowledge_base_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot has no knowledge base bound — cannot compile wiki",
        )

    # Lazy resolve: background task must fetch a *new* use_case instance
    # from the Container (with a fresh independent session). Using the
    # request-scoped injected instance would leak the closed session.
    async def _compile(cmd: CompileWikiCommand) -> None:
        uc = Container.compile_wiki_use_case()
        await uc.execute(cmd)

    command = CompileWikiCommand(
        bot_id=bot_id,
        tenant_id=tenant.tenant_id,
    )
    background_tasks.add_task(
        safe_background_task,
        _compile,
        command,
        task_name="compile_wiki",
        tenant_id=tenant.tenant_id,
    )
    return CompileWikiResponse(
        bot_id=bot_id,
        status="accepted",
        message=(
            "Wiki compilation started in background — "
            "poll /wiki/status for progress"
        ),
    )


@router.get(
    "/{bot_id}/wiki/status",
    response_model=WikiStatusResponse,
)
@inject
async def get_wiki_status(
    bot_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetWikiStatusUseCase = Depends(
        Provide[Container.get_wiki_status_use_case]
    ),
) -> WikiStatusResponse:
    try:
        view = await use_case.execute(tenant.tenant_id, bot_id)
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No wiki graph found for bot '{bot_id}' — trigger compile first",
        ) from None
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None

    meta = view.metadata or {}
    return WikiStatusResponse(
        wiki_graph_id=view.wiki_graph_id,
        bot_id=view.bot_id,
        kb_id=view.kb_id,
        status=view.status,
        node_count=view.node_count,
        edge_count=view.edge_count,
        cluster_count=view.cluster_count,
        doc_count=view.doc_count,
        compiled_at=view.compiled_at.isoformat() if view.compiled_at else None,
        token_usage=meta.get("token_usage"),
        errors=meta.get("errors"),
    )
