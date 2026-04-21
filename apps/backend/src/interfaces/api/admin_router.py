from math import ceil

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from dataclasses import asdict

from src.application.auth.delete_user_use_case import DeleteUserUseCase
from src.application.auth.get_user_use_case import GetUserUseCase
from src.application.auth.list_users_use_case import ListUsersUseCase
from src.application.billing.get_billing_dashboard_use_case import (
    GetBillingDashboardUseCase,
)
from src.application.conversation.search_conversations_use_case import (
    SearchConversationsUseCase,
)
from src.application.billing.list_quota_events_use_case import (
    ListQuotaEventsUseCase,
)
from src.application.ledger.list_all_tenants_quotas_use_case import (
    ListAllTenantsQuotasUseCase,
)
from src.domain.ledger.entity import current_year_month
from datetime import datetime
from decimal import Decimal
from src.application.auth.register_user_use_case import (
    RegisterUserCommand,
    RegisterUserUseCase,
)
from src.application.auth.reset_password_use_case import (
    ResetPasswordCommand,
    ResetPasswordUseCase,
)
from src.application.auth.update_user_use_case import (
    UpdateUserCommand,
    UpdateUserUseCase,
)
from src.application.ratelimit.get_rate_limits_use_case import GetRateLimitsUseCase
from src.domain.ratelimit.entity import RateLimitConfig as RLConfig
from src.domain.ratelimit.repository import RateLimitConfigRepository
from src.domain.ratelimit.value_objects import EndpointGroup
from src.application.ratelimit.update_rate_limit_use_case import (
    UpdateRateLimitCommand,
    UpdateRateLimitUseCase,
)
from src.container import Container
from src.domain.auth.entity import InvalidTenantBindingError, TenantRequiredError
from src.domain.shared.exceptions import DuplicateEntityError, EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, require_role
from src.interfaces.api.schemas.pagination import PaginatedResponse, PaginationQuery

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class RateLimitConfigResponse(BaseModel):
    endpoint_group: str
    requests_per_minute: int
    burst_size: int
    per_user_requests_per_minute: int | None = None
    tenant_id: str | None = None


class UpdateRateLimitRequest(BaseModel):
    endpoint_group: str
    requests_per_minute: int
    burst_size: int
    per_user_requests_per_minute: int | None = None


@router.get(
    "/rate-limits/defaults",
    response_model=list[RateLimitConfigResponse],
)
@inject
async def get_default_rate_limits(
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    repo: RateLimitConfigRepository = Depends(
        Provide[Container.rate_limit_config_repository]
    ),
) -> list[RateLimitConfigResponse]:
    """Get global default rate limit configs (tenant_id=None)."""
    defaults = await repo.find_defaults()
    result: dict[str, RateLimitConfigResponse] = {}
    for cfg in defaults:
        result[cfg.endpoint_group.value] = RateLimitConfigResponse(
            endpoint_group=cfg.endpoint_group.value,
            requests_per_minute=cfg.requests_per_minute,
            burst_size=cfg.burst_size,
            per_user_requests_per_minute=cfg.per_user_requests_per_minute,
            tenant_id=cfg.tenant_id,
        )
    # Fill missing groups with hardcoded fallback
    for group in EndpointGroup:
        if group.value not in result:
            fallback = RLConfig(endpoint_group=group)
            result[group.value] = RateLimitConfigResponse(
                endpoint_group=group.value,
                requests_per_minute=fallback.requests_per_minute,
                burst_size=fallback.burst_size,
                per_user_requests_per_minute=fallback.per_user_requests_per_minute,
                tenant_id=None,
            )
    return list(result.values())


@router.put(
    "/rate-limits/defaults",
    response_model=RateLimitConfigResponse,
)
@inject
async def update_default_rate_limit(
    body: UpdateRateLimitRequest,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: UpdateRateLimitUseCase = Depends(
        Provide[Container.update_rate_limit_use_case]
    ),
) -> RateLimitConfigResponse:
    """Create or update a global default rate limit config."""
    command = UpdateRateLimitCommand(
        tenant_id=None,
        endpoint_group=body.endpoint_group,
        requests_per_minute=body.requests_per_minute,
        burst_size=body.burst_size,
        per_user_requests_per_minute=body.per_user_requests_per_minute,
        caller_role=admin.role or "",
    )
    config = await use_case.execute(command)
    return RateLimitConfigResponse(
        endpoint_group=config.endpoint_group.value,
        requests_per_minute=config.requests_per_minute,
        burst_size=config.burst_size,
        per_user_requests_per_minute=config.per_user_requests_per_minute,
        tenant_id=config.tenant_id,
    )


@router.get(
    "/rate-limits/{tenant_id}",
    response_model=list[RateLimitConfigResponse],
)
@inject
async def get_rate_limits(
    tenant_id: str,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: GetRateLimitsUseCase = Depends(
        Provide[Container.get_rate_limits_use_case]
    ),
) -> list[RateLimitConfigResponse]:
    """Get merged rate limit configs for a tenant (defaults + overrides)."""
    configs = await use_case.execute(tenant_id)
    return [
        RateLimitConfigResponse(
            endpoint_group=cfg.endpoint_group.value,
            requests_per_minute=cfg.requests_per_minute,
            burst_size=cfg.burst_size,
            per_user_requests_per_minute=cfg.per_user_requests_per_minute,
            tenant_id=cfg.tenant_id,
        )
        for cfg in configs.values()
    ]


@router.put(
    "/rate-limits/{tenant_id}",
    response_model=RateLimitConfigResponse,
)
@inject
async def update_rate_limit(
    tenant_id: str,
    body: UpdateRateLimitRequest,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: UpdateRateLimitUseCase = Depends(
        Provide[Container.update_rate_limit_use_case]
    ),
) -> RateLimitConfigResponse:
    """Create or update a rate limit config for a tenant."""
    command = UpdateRateLimitCommand(
        tenant_id=tenant_id,
        endpoint_group=body.endpoint_group,
        requests_per_minute=body.requests_per_minute,
        burst_size=body.burst_size,
        per_user_requests_per_minute=body.per_user_requests_per_minute,
        caller_role=admin.role or "",
    )
    config = await use_case.execute(command)
    return RateLimitConfigResponse(
        endpoint_group=config.endpoint_group.value,
        requests_per_minute=config.requests_per_minute,
        burst_size=config.burst_size,
        per_user_requests_per_minute=config.per_user_requests_per_minute,
        tenant_id=config.tenant_id,
    )


# --- User Management ---


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: str
    role: str
    created_at: str
    updated_at: str


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str = "user"
    tenant_id: str


class UpdateUserRequest(BaseModel):
    role: str | None = None
    tenant_id: str | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str


def _user_response(user) -> UserResponse:
    return UserResponse(
        id=user.id.value,
        tenant_id=user.tenant_id or "",
        email=user.email.value,
        role=user.role.value,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@router.get("/users", response_model=PaginatedResponse[UserResponse])
@inject
async def list_users(
    tenant_id: str | None = None,
    pagination: PaginationQuery = Depends(),
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ListUsersUseCase = Depends(
        Provide[Container.list_users_use_case]
    ),
) -> PaginatedResponse[UserResponse]:
    limit = pagination.page_size
    offset = (pagination.page - 1) * pagination.page_size
    users = await use_case.execute(
        tenant_id, limit=limit, offset=offset,
    )
    total = await use_case.count(tenant_id)
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[_user_response(u) for u in users],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_user(
    body: CreateUserRequest,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: RegisterUserUseCase = Depends(
        Provide[Container.register_user_use_case]
    ),
) -> UserResponse:
    try:
        user = await use_case.execute(
            RegisterUserCommand(
                email=body.email,
                password=body.password,
                role=body.role,
                tenant_id=body.tenant_id,
            )
        )
    except DuplicateEntityError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=e.message) from None
    except (InvalidTenantBindingError, TenantRequiredError) as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message
        ) from None
    return _user_response(user)


@router.get("/users/{user_id}", response_model=UserResponse)
@inject
async def get_user(
    user_id: str,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: GetUserUseCase = Depends(
        Provide[Container.get_user_use_case]
    ),
) -> UserResponse:
    try:
        user = await use_case.execute(user_id)
    except EntityNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None
    return _user_response(user)


@router.put("/users/{user_id}", response_model=UserResponse)
@inject
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: UpdateUserUseCase = Depends(
        Provide[Container.update_user_use_case]
    ),
) -> UserResponse:
    try:
        user = await use_case.execute(
            UpdateUserCommand(
                user_id=user_id,
                role=body.role,
                tenant_id=body.tenant_id,
            )
        )
    except EntityNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None
    except (InvalidTenantBindingError, TenantRequiredError) as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message
        ) from None
    return _user_response(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_user(
    user_id: str,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: DeleteUserUseCase = Depends(
        Provide[Container.delete_user_use_case]
    ),
) -> None:
    try:
        await use_case.execute(user_id)
    except EntityNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None


@router.post(
    "/users/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
)
@inject
async def reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ResetPasswordUseCase = Depends(
        Provide[Container.reset_password_use_case]
    ),
) -> None:
    try:
        await use_case.execute(
            ResetPasswordCommand(
                user_id=user_id,
                new_password=body.new_password,
            )
        )
    except EntityNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="User not found"
        ) from None


# --- Tenant Quota Overview (S-Token-Gov.2.5) ---


class TenantQuotaOverviewResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    plan_name: str
    cycle_year_month: str
    base_total: int
    base_remaining: int
    addon_remaining: int
    total_remaining: int
    total_used_in_cycle: int
    included_categories: list[str] | None = None
    has_ledger: bool


@router.get(
    "/tenants/quotas",
    response_model=list[TenantQuotaOverviewResponse],
)
@inject
async def list_all_tenants_quotas(
    cycle: str | None = Query(
        None, description="YYYY-MM format; defaults to current month"
    ),
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ListAllTenantsQuotasUseCase = Depends(
        Provide[Container.list_all_tenants_quotas_use_case]
    ),
) -> list[TenantQuotaOverviewResponse]:
    """List all tenants' quota for a given cycle (system_admin only)."""
    target_cycle = cycle or current_year_month()
    items = await use_case.execute(target_cycle)
    return [TenantQuotaOverviewResponse(**asdict(i)) for i in items]


# --- Quota Events (S-Token-Gov.3) ---


class QuotaEventResponse(BaseModel):
    event_id: str
    event_type: str
    tenant_id: str
    tenant_name: str
    cycle_year_month: str
    created_at: datetime
    addon_tokens_added: int | None = None
    amount_currency: str | None = None
    amount_value: Decimal | None = None
    used_ratio: Decimal | None = None
    message: str | None = None
    reason: str | None = None
    delivered_to_email: bool | None = None


@router.get(
    "/quota-events",
    response_model=PaginatedResponse[QuotaEventResponse],
)
@inject
async def list_quota_events(
    tenant_id: str | None = None,
    pagination: PaginationQuery = Depends(),
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ListQuotaEventsUseCase = Depends(
        Provide[Container.list_quota_events_use_case]
    ),
) -> PaginatedResponse[QuotaEventResponse]:
    """List auto-topup events + quota threshold alerts merged by created_at desc."""
    items, total = await use_case.execute(
        tenant_id=tenant_id,
        limit=pagination.page_size,
        offset=(pagination.page - 1) * pagination.page_size,
    )
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[
            QuotaEventResponse(
                event_id=i.event_id,
                event_type=i.event_type,
                tenant_id=i.tenant_id,
                tenant_name=i.tenant_name,
                cycle_year_month=i.cycle_year_month,
                created_at=i.created_at,
                addon_tokens_added=i.addon_tokens_added,
                amount_currency=i.amount_currency,
                amount_value=i.amount_value,
                used_ratio=i.used_ratio,
                message=i.message,
                reason=i.reason,
                delivered_to_email=i.delivered_to_email,
            )
            for i in items
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


# --- Billing Dashboard (S-Token-Gov.4) ---


class MonthlyRevenuePointResponse(BaseModel):
    cycle_year_month: str
    total_amount: Decimal
    transaction_count: int
    addon_tokens_total: int


class PlanRevenuePointResponse(BaseModel):
    plan_name: str
    total_amount: Decimal
    transaction_count: int


class TopTenantItemResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    total_amount: Decimal
    transaction_count: int


class BillingDashboardResponse(BaseModel):
    monthly_revenue: list[MonthlyRevenuePointResponse]
    by_plan: list[PlanRevenuePointResponse]
    top_tenants: list[TopTenantItemResponse]
    total_revenue: Decimal
    total_transactions: int
    cycle_start: str
    cycle_end: str


def _calc_start_cycle(end_cycle: str, *, months_back: int) -> str:
    """從 end_cycle (YYYY-MM) 往前 N 個月，回傳 start_cycle 字串。"""
    year, month = end_cycle.split("-")
    y, m = int(year), int(month)
    # 往前 months_back-1 個月（含當月共 months_back 個月）
    for _ in range(months_back - 1):
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    return f"{y:04d}-{m:02d}"


@router.get(
    "/billing/dashboard",
    response_model=BillingDashboardResponse,
)
@inject
async def get_billing_dashboard(
    start: str | None = Query(None, description="YYYY-MM, defaults to 6 months back"),
    end: str | None = Query(None, description="YYYY-MM, defaults to current month"),
    top_n: int = Query(10, ge=1, le=50),
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: GetBillingDashboardUseCase = Depends(
        Provide[Container.get_billing_dashboard_use_case]
    ),
) -> BillingDashboardResponse:
    """Aggregated billing data for revenue dashboard (system_admin only)."""
    end_cycle = end or current_year_month()
    start_cycle = start or _calc_start_cycle(end_cycle, months_back=6)
    result = await use_case.execute(
        start_cycle=start_cycle, end_cycle=end_cycle, top_n=top_n,
    )
    return BillingDashboardResponse(
        monthly_revenue=[
            MonthlyRevenuePointResponse(**asdict(m))
            for m in result.monthly_revenue
        ],
        by_plan=[
            PlanRevenuePointResponse(**asdict(p)) for p in result.by_plan
        ],
        top_tenants=[
            TopTenantItemResponse(**asdict(t)) for t in result.top_tenants
        ],
        total_revenue=result.total_revenue,
        total_transactions=result.total_transactions,
        cycle_start=result.cycle_start,
        cycle_end=result.cycle_end,
    )


# --- Conversation Hybrid Search (S-Gov.6b) ---


class ConversationSearchResultResponse(BaseModel):
    conversation_id: str
    tenant_id: str
    tenant_name: str
    bot_id: str | None = None
    summary: str
    first_message_at: str | None = None
    last_message_at: str | None = None
    message_count: int
    score: float | None = None  # 僅 semantic 模式有
    matched_via: str  # "keyword" | "semantic"


@router.get(
    "/conversations/search",
    response_model=list[ConversationSearchResultResponse],
)
@inject
async def search_conversations(
    keyword: str | None = Query(
        None, description="PG ILIKE on summary（精準字面）"
    ),
    semantic: str | None = Query(
        None, description="Milvus vector search（語意相近）"
    ),
    tenant_id: str | None = Query(
        None, description="限定租戶（admin 跨租戶可省略）"
    ),
    bot_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    _admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: SearchConversationsUseCase = Depends(
        Provide[Container.search_conversations_use_case]
    ),
) -> list[ConversationSearchResultResponse]:
    """S-Gov.6b: keyword (PG ILIKE) 或 semantic (Milvus vector) 搜對話摘要。
    兩者擇一傳入；不可同時。
    """
    if not keyword and not semantic:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="需提供 keyword 或 semantic 至少一個",
        )
    if keyword and semantic:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="keyword 與 semantic 互斥，請擇一",
        )

    if keyword:
        items = await use_case.search_by_keyword(
            keyword=keyword,
            tenant_id=tenant_id,
            bot_id=bot_id,
            limit=limit,
        )
    else:
        items = await use_case.search_by_semantic(
            query=semantic,  # type: ignore[arg-type]
            tenant_id=tenant_id,
            bot_id=bot_id,
            limit=limit,
        )

    return [
        ConversationSearchResultResponse(
            conversation_id=i.conversation_id,
            tenant_id=i.tenant_id,
            tenant_name=i.tenant_name,
            bot_id=i.bot_id,
            summary=i.summary,
            first_message_at=i.first_message_at,
            last_message_at=i.last_message_at,
            message_count=i.message_count,
            score=i.score,
            matched_via=i.matched_via,
        )
        for i in items
    ]
