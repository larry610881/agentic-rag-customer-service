"""Bot Management API 端點"""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.bot.create_bot_use_case import (
    CreateBotCommand,
    CreateBotUseCase,
)
from src.application.bot.delete_bot_use_case import DeleteBotUseCase
from src.application.bot.get_bot_use_case import GetBotUseCase
from src.application.bot.list_bots_use_case import ListBotsUseCase
from src.application.bot.update_bot_use_case import UpdateBotCommand, UpdateBotUseCase
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(prefix="/api/v1/bots", tags=["bots"])


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
    enabled_tools: list[str] = ["rag_query"]
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
    enabled_tools: list[str] | None = None
    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None


class BotResponse(BaseModel):
    id: str
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
    enabled_tools: list[str]
    line_channel_secret: str | None
    line_channel_access_token: str | None
    created_at: str
    updated_at: str


def _to_response(bot) -> BotResponse:
    return BotResponse(
        id=bot.id.value,
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
        enabled_tools=bot.enabled_tools,
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
            enabled_tools=body.enabled_tools,
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
) -> list[BotResponse]:
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
    kwargs: dict = {"bot_id": bot_id}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.description is not None:
        kwargs["description"] = body.description
    if body.is_active is not None:
        kwargs["is_active"] = body.is_active
    if body.knowledge_base_ids is not None:
        kwargs["knowledge_base_ids"] = body.knowledge_base_ids
    if body.system_prompt is not None:
        kwargs["system_prompt"] = body.system_prompt
    if body.temperature is not None:
        kwargs["temperature"] = body.temperature
    if body.max_tokens is not None:
        kwargs["max_tokens"] = body.max_tokens
    if body.history_limit is not None:
        kwargs["history_limit"] = body.history_limit
    if body.frequency_penalty is not None:
        kwargs["frequency_penalty"] = body.frequency_penalty
    if body.reasoning_effort is not None:
        kwargs["reasoning_effort"] = body.reasoning_effort
    if body.enabled_tools is not None:
        kwargs["enabled_tools"] = body.enabled_tools
    if body.line_channel_secret is not None:
        kwargs["line_channel_secret"] = body.line_channel_secret
    if body.line_channel_access_token is not None:
        kwargs["line_channel_access_token"] = body.line_channel_access_token

    try:
        bot = await use_case.execute(UpdateBotCommand(**kwargs))
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
