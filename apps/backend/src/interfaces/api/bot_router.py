"""Bot Management API 端點"""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any

from pydantic import BaseModel

from src.application.bot.create_bot_use_case import (
    CreateBotCommand,
    CreateBotUseCase,
)
from src.application.bot.list_all_bots_use_case import ListAllBotsUseCase
from src.application.bot.delete_bot_use_case import DeleteBotUseCase
from src.application.bot.get_bot_use_case import GetBotUseCase
from src.application.bot.list_bots_use_case import ListBotsUseCase
from src.application.bot.update_bot_use_case import UpdateBotCommand, UpdateBotUseCase
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(prefix="/api/v1/bots", tags=["bots"])


_VALID_AGENT_MODES = {"router", "react"}
_VALID_AUDIT_MODES = {"off", "minimal", "full"}
_VALID_EVAL_DEPTHS = {
    "off", "L1", "L2", "L3",
    "L1+L2", "L1+L3", "L2+L3",
    "L1+L2+L3",
}


class CreateBotRequest(BaseModel):
    name: str
    description: str = ""
    knowledge_base_ids: list[str] = []
    system_prompt: str = ""
    is_active: bool = True
    temperature: float = 0.3
    max_tokens: int = 1024
    history_limit: int = 10
    frequency_penalty: float = 0.0
    reasoning_effort: str = "medium"
    rag_top_k: int = 5
    rag_score_threshold: float = 0.3
    enabled_tools: list[str] = ["rag_query"]
    llm_provider: str = ""
    llm_model: str = ""
    show_sources: bool = True
    agent_mode: str = "router"
    audit_mode: str = "minimal"
    eval_provider: str = ""
    eval_model: str = ""
    eval_depth: str = "L1"
    mcp_servers: list[dict[str, Any]] = []
    max_tool_calls: int = 5
    base_prompt: str = ""
    router_prompt: str = ""
    react_prompt: str = ""
    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None


class UpdateBotRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    knowledge_base_ids: list[str] | None = None
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    history_limit: int | None = None
    frequency_penalty: float | None = None
    reasoning_effort: str | None = None
    rag_top_k: int | None = None
    rag_score_threshold: float | None = None
    enabled_tools: list[str] | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    show_sources: bool | None = None
    agent_mode: str | None = None
    audit_mode: str | None = None
    eval_provider: str | None = None
    eval_model: str | None = None
    eval_depth: str | None = None
    mcp_servers: list[dict[str, Any]] | None = None
    max_tool_calls: int | None = None
    base_prompt: str | None = None
    router_prompt: str | None = None
    react_prompt: str | None = None
    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None


class BotResponse(BaseModel):
    id: str
    short_code: str
    tenant_id: str
    name: str
    description: str
    is_active: bool
    system_prompt: str
    knowledge_base_ids: list[str]
    temperature: float
    max_tokens: int
    history_limit: int
    frequency_penalty: float
    reasoning_effort: str
    rag_top_k: int
    rag_score_threshold: float
    enabled_tools: list[str]
    llm_provider: str
    llm_model: str
    show_sources: bool
    agent_mode: str
    audit_mode: str
    eval_provider: str
    eval_model: str
    eval_depth: str
    mcp_servers: list[dict[str, Any]]
    max_tool_calls: int
    base_prompt: str
    router_prompt: str
    react_prompt: str
    line_channel_secret: str | None
    line_channel_access_token: str | None
    created_at: str
    updated_at: str


def _to_response(bot) -> BotResponse:
    return BotResponse(
        id=bot.id.value,
        short_code=bot.short_code.value,
        tenant_id=bot.tenant_id,
        name=bot.name,
        description=bot.description,
        is_active=bot.is_active,
        system_prompt=bot.system_prompt,
        knowledge_base_ids=bot.knowledge_base_ids,
        temperature=bot.llm_params.temperature,
        max_tokens=bot.llm_params.max_tokens,
        history_limit=bot.llm_params.history_limit,
        frequency_penalty=bot.llm_params.frequency_penalty,
        reasoning_effort=bot.llm_params.reasoning_effort,
        rag_top_k=bot.llm_params.rag_top_k,
        rag_score_threshold=bot.llm_params.rag_score_threshold,
        enabled_tools=bot.enabled_tools,
        llm_provider=bot.llm_provider,
        llm_model=bot.llm_model,
        show_sources=bot.show_sources,
        agent_mode=bot.agent_mode,
        audit_mode=bot.audit_mode,
        eval_provider=bot.eval_provider,
        eval_model=bot.eval_model,
        eval_depth=bot.eval_depth,
        mcp_servers=[
            {
                "url": s.url,
                "name": s.name,
                "enabled_tools": s.enabled_tools,
                "tools": [{"name": t.name, "description": t.description} for t in s.tools],
                "version": s.version,
            }
            for s in bot.mcp_servers
        ],
        max_tool_calls=bot.max_tool_calls,
        base_prompt=bot.base_prompt,
        router_prompt=bot.router_prompt,
        react_prompt=bot.react_prompt,
        line_channel_secret=bot.line_channel_secret,
        line_channel_access_token=bot.line_channel_access_token,
        created_at=bot.created_at.isoformat(),
        updated_at=bot.updated_at.isoformat(),
    )


@router.post(
    "",
    response_model=BotResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_bot(
    body: CreateBotRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: CreateBotUseCase = Depends(
        Provide[Container.create_bot_use_case]
    ),
) -> BotResponse:
    if body.agent_mode not in _VALID_AGENT_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"agent_mode must be one of {sorted(_VALID_AGENT_MODES)}",
        )
    if body.audit_mode not in _VALID_AUDIT_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"audit_mode must be one of {sorted(_VALID_AUDIT_MODES)}",
        )
    if body.eval_depth not in _VALID_EVAL_DEPTHS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"eval_depth must be one of {sorted(_VALID_EVAL_DEPTHS)}",
        )
    bot = await use_case.execute(
        CreateBotCommand(
            tenant_id=tenant.tenant_id,
            name=body.name,
            description=body.description,
            knowledge_base_ids=body.knowledge_base_ids,
            system_prompt=body.system_prompt,
            is_active=body.is_active,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            history_limit=body.history_limit,
            frequency_penalty=body.frequency_penalty,
            reasoning_effort=body.reasoning_effort,
            rag_top_k=body.rag_top_k,
            rag_score_threshold=body.rag_score_threshold,
            enabled_tools=body.enabled_tools,
            llm_provider=body.llm_provider,
            llm_model=body.llm_model,
            show_sources=body.show_sources,
            agent_mode=body.agent_mode,
            audit_mode=body.audit_mode,
            eval_provider=body.eval_provider,
            eval_model=body.eval_model,
            eval_depth=body.eval_depth,
            mcp_servers=body.mcp_servers,
            max_tool_calls=body.max_tool_calls,
            base_prompt=body.base_prompt,
            router_prompt=body.router_prompt,
            react_prompt=body.react_prompt,
            line_channel_secret=body.line_channel_secret,
            line_channel_access_token=body.line_channel_access_token,
        )
    )
    return _to_response(bot)


@router.get("", response_model=list[BotResponse])
@inject
async def list_bots(
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListBotsUseCase = Depends(
        Provide[Container.list_bots_use_case]
    ),
    list_all_use_case: ListAllBotsUseCase = Depends(
        Provide[Container.list_all_bots_use_case]
    ),
) -> list[BotResponse]:
    if tenant.role == "system_admin":
        bots = await list_all_use_case.execute()
    else:
        bots = await use_case.execute(tenant.tenant_id)
    return [_to_response(b) for b in bots]


@router.get("/{bot_id}", response_model=BotResponse)
@inject
async def get_bot(
    bot_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetBotUseCase = Depends(
        Provide[Container.get_bot_use_case]
    ),
) -> BotResponse:
    try:
        bot = await use_case.execute(bot_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None
    return _to_response(bot)


def _build_update_command(
    bot_id: str, body: UpdateBotRequest
) -> UpdateBotCommand:
    """Build UpdateBotCommand from request, only including set fields."""
    kwargs: dict = {"bot_id": bot_id}
    for field in body.model_fields_set:
        kwargs[field] = getattr(body, field)
    return UpdateBotCommand(**kwargs)


@router.put("/{bot_id}", response_model=BotResponse)
@inject
async def update_bot(
    bot_id: str,
    body: UpdateBotRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: UpdateBotUseCase = Depends(
        Provide[Container.update_bot_use_case]
    ),
) -> BotResponse:
    if body.agent_mode is not None and body.agent_mode not in _VALID_AGENT_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"agent_mode must be one of {sorted(_VALID_AGENT_MODES)}",
        )
    if body.audit_mode is not None and body.audit_mode not in _VALID_AUDIT_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"audit_mode must be one of {sorted(_VALID_AUDIT_MODES)}",
        )
    if body.eval_depth is not None and body.eval_depth not in _VALID_EVAL_DEPTHS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"eval_depth must be one of {sorted(_VALID_EVAL_DEPTHS)}",
        )
    command = _build_update_command(bot_id, body)
    try:
        bot = await use_case.execute(command)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None
    return _to_response(bot)


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_bot(
    bot_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: DeleteBotUseCase = Depends(
        Provide[Container.delete_bot_use_case]
    ),
) -> None:
    try:
        await use_case.execute(bot_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None
