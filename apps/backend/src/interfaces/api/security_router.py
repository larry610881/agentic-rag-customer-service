from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.application.security.guard_rules_use_cases import (
    GetGuardRulesUseCase,
    UpdateGuardRulesCommand,
    UpdateGuardRulesUseCase,
    ResetGuardRulesUseCase,
)
from src.container import Container
from src.domain.security.guard_config import GuardLogRepository
from src.interfaces.api.deps import CurrentTenant, get_current_tenant, require_role
from src.interfaces.api.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/api/v1/security", tags=["security"])


class GuardRuleItem(BaseModel):
    pattern: str
    type: str = "regex"
    enabled: bool = True


class OutputKeywordItem(BaseModel):
    keyword: str
    enabled: bool = True


class GuardRulesResponse(BaseModel):
    id: str
    input_rules: list[dict]
    output_keywords: list[dict]
    llm_guard_enabled: bool
    llm_guard_model: str
    input_guard_prompt: str
    output_guard_prompt: str
    blocked_response: str
    updated_at: str


class UpdateGuardRulesRequest(BaseModel):
    input_rules: list[GuardRuleItem]
    output_keywords: list[OutputKeywordItem]
    llm_guard_enabled: bool = False
    llm_guard_model: str = ""
    input_guard_prompt: str = ""
    output_guard_prompt: str = ""
    blocked_response: str = "我只能協助您處理客服相關問題。"


class GuardLogItem(BaseModel):
    id: str
    tenant_id: str
    bot_id: str | None
    user_id: str | None
    log_type: str
    rule_matched: str
    user_message: str
    ai_response: str | None
    created_at: str


@router.get("/guard-rules", response_model=GuardRulesResponse)
@inject
async def get_guard_rules(
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: GetGuardRulesUseCase = Depends(
        Provide[Container.get_guard_rules_use_case]
    ),
) -> GuardRulesResponse:
    config = await use_case.execute()
    return GuardRulesResponse(
        id=config.id,
        input_rules=config.input_rules,
        output_keywords=config.output_keywords,
        llm_guard_enabled=config.llm_guard_enabled,
        llm_guard_model=config.llm_guard_model,
        input_guard_prompt=config.input_guard_prompt,
        output_guard_prompt=config.output_guard_prompt,
        blocked_response=config.blocked_response,
        updated_at=config.updated_at.isoformat(),
    )


@router.put("/guard-rules", response_model=GuardRulesResponse)
@inject
async def update_guard_rules(
    body: UpdateGuardRulesRequest,
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: UpdateGuardRulesUseCase = Depends(
        Provide[Container.update_guard_rules_use_case]
    ),
) -> GuardRulesResponse:
    config = await use_case.execute(
        UpdateGuardRulesCommand(
            input_rules=[r.model_dump() for r in body.input_rules],
            output_keywords=[k.model_dump() for k in body.output_keywords],
            llm_guard_enabled=body.llm_guard_enabled,
            llm_guard_model=body.llm_guard_model,
            input_guard_prompt=body.input_guard_prompt,
            output_guard_prompt=body.output_guard_prompt,
            blocked_response=body.blocked_response,
        )
    )
    return GuardRulesResponse(
        id=config.id,
        input_rules=config.input_rules,
        output_keywords=config.output_keywords,
        llm_guard_enabled=config.llm_guard_enabled,
        llm_guard_model=config.llm_guard_model,
        input_guard_prompt=config.input_guard_prompt,
        output_guard_prompt=config.output_guard_prompt,
        blocked_response=config.blocked_response,
        updated_at=config.updated_at.isoformat(),
    )


@router.post("/guard-rules/reset", response_model=GuardRulesResponse)
@inject
async def reset_guard_rules(
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ResetGuardRulesUseCase = Depends(
        Provide[Container.reset_guard_rules_use_case]
    ),
) -> GuardRulesResponse:
    config = await use_case.execute()
    return GuardRulesResponse(
        id=config.id,
        input_rules=config.input_rules,
        output_keywords=config.output_keywords,
        llm_guard_enabled=config.llm_guard_enabled,
        llm_guard_model=config.llm_guard_model,
        input_guard_prompt=config.input_guard_prompt,
        output_guard_prompt=config.output_guard_prompt,
        blocked_response=config.blocked_response,
        updated_at=config.updated_at.isoformat(),
    )


@router.get("/guard-logs", response_model=PaginatedResponse[GuardLogItem])
@inject
async def list_guard_logs(
    log_type: str | None = Query(default=None),
    bot_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: CurrentTenant = Depends(require_role("system_admin")),
    log_repo: GuardLogRepository = Depends(
        Provide[Container.guard_log_repository]
    ),
) -> PaginatedResponse[GuardLogItem]:
    from math import ceil
    offset = (page - 1) * page_size
    logs = await log_repo.find_logs(
        log_type=log_type, bot_id=bot_id, limit=page_size, offset=offset
    )
    total = await log_repo.count_logs(log_type=log_type, bot_id=bot_id)
    total_pages = ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[GuardLogItem(**log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
