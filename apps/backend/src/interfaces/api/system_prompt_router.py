"""System Prompt Config API — 系統層級 Prompt 管理"""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.application.platform.system_prompt_use_cases import (
    GetSystemPromptsUseCase,
    UpdateSystemPromptsCommand,
    UpdateSystemPromptsUseCase,
)
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, get_current_tenant, require_role

router = APIRouter(prefix="/api/v1/system/prompts", tags=["system-prompts"])


class SystemPromptConfigResponse(BaseModel):
    base_prompt: str
    updated_at: str


class UpdateSystemPromptConfigRequest(BaseModel):
    base_prompt: str = ""


@router.get("", response_model=SystemPromptConfigResponse)
@inject
async def get_system_prompts(
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetSystemPromptsUseCase = Depends(
        Provide[Container.get_system_prompts_use_case]
    ),
) -> SystemPromptConfigResponse:
    config = await use_case.execute()
    return SystemPromptConfigResponse(
        base_prompt=config.base_prompt,
        updated_at=config.updated_at.isoformat(),
    )


@router.put("", response_model=SystemPromptConfigResponse)
@inject
async def update_system_prompts(
    body: UpdateSystemPromptConfigRequest,
    tenant: CurrentTenant = Depends(require_role("system_admin")),
    use_case: UpdateSystemPromptsUseCase = Depends(
        Provide[Container.update_system_prompts_use_case]
    ),
) -> SystemPromptConfigResponse:
    config = await use_case.execute(
        UpdateSystemPromptsCommand(
            base_prompt=body.base_prompt,
        )
    )
    return SystemPromptConfigResponse(
        base_prompt=config.base_prompt,
        updated_at=config.updated_at.isoformat(),
    )
