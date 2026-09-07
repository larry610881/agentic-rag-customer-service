from math import ceil

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.quota.compute_tenant_quota_use_case import (
    ComputeTenantQuotaUseCase,
)
from src.application.tenant.create_tenant_use_case import (
    CreateTenantCommand,
    CreateTenantUseCase,
)
from src.application.tenant.get_tenant_use_case import GetTenantUseCase
from src.application.tenant.list_tenants_use_case import ListTenantsUseCase
from src.application.tenant.notification_preferences_use_cases import (
    GetTenantNotificationPreferencesUseCase,
    TenantNotificationPreferencesView,
    UpdateTenantNotificationPreferencesUseCase,
)
from src.application.tenant.update_tenant_billing_policy_use_case import (
    UpdateTenantBillingPolicyUseCase,
)
from src.application.tenant.update_tenant_use_case import (
    UpdateTenantCommand,
    UpdateTenantUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import (
    DomainException,
    DuplicateEntityError,
    EntityNotFoundError,
    ValidationError,
)
from src.domain.tenant.entity import Tenant
from src.interfaces.api.deps import CurrentTenant, get_current_tenant, require_role
from src.interfaces.api.schemas.pagination import PaginatedResponse, PaginationQuery

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


class CreateTenantRequest(BaseModel):
    name: str
    plan: str = "starter"


class UpdateTenantConfigRequest(BaseModel):
    plan: str | None = None
    prompt_gate_enabled: bool | None = None
    monthly_token_limit: int | None = None
    included_categories: list[str] | None = None
    default_ocr_model: str | None = None
    default_context_model: str | None = None
    default_classification_model: str | None = None
    default_summary_model: str | None = None
    default_intent_model: str | None = None


class TenantQuotaResponse(BaseModel):
    """租戶視角配額 — S-Ledger-Unification P5

    租戶頁只顯示 billable（= 影響自身帳單的量）。
    total_audit_in_cycle 僅供系統管理員 API 使用，不暴露於此端點。
    """

    cycle_year_month: str
    plan_name: str
    base_total: int
    base_remaining: int
    addon_remaining: int
    total_remaining: int
    total_billable_in_cycle: int  # 取代 total_used_in_cycle（breaking rename）
    included_categories: list[str] | None = None
    # Issue #74：雙軌計價 + 用盡策略（token 制租戶 points_* 恆 0）
    billing_mode: str = "token"
    exhaustion_policy: str = "auto_topup"  # 方案預設
    effective_policy: str = "auto_topup"  # 租戶覆寫後生效
    tenant_may_change_policy: bool = False
    grace_percent: float = 0.0
    block_message: str = ""
    points_total: int = 0
    points_used: int = 0
    points_remaining: int = 0


class UpdateTenantBillingPolicyRequest(BaseModel):
    """Issue #74：null = 沿用方案（清除覆寫）。"""

    exhaustion_policy: str | None = None
    block_message: str | None = None


class TenantBillingPolicyResponse(BaseModel):
    tenant_id: str
    exhaustion_policy_override: str | None = None
    block_message_override: str | None = None
    effective_policy: str
    block_message: str
    tenant_may_change_policy: bool


class UpdateNotificationPreferencesRequest(BaseModel):
    """Issue #77：要通知的欄位群組；null = 平台預設（model + prompt）；
    [] = 完全關閉。"""

    config_change_notify_fields: list[str] | None = None


class NotifyGroupOptionResponse(BaseModel):
    key: str
    label: str


class TenantNotificationPreferencesResponse(BaseModel):
    tenant_id: str
    config_change_notify_fields: list[str] | None = None
    effective_fields: list[str]
    available_groups: list[NotifyGroupOptionResponse]


def _preferences_response(
    view: TenantNotificationPreferencesView,
) -> TenantNotificationPreferencesResponse:
    return TenantNotificationPreferencesResponse(
        tenant_id=view.tenant_id,
        config_change_notify_fields=view.fields,
        effective_fields=view.effective,
        available_groups=[
            NotifyGroupOptionResponse(key=g.key, label=g.label)
            for g in view.available_groups
        ],
    )


def _resolve_tenant_alias(tenant_id: str, caller: CurrentTenant) -> str:
    """Issue #74：`me` 代表呼叫者自己的租戶。"""
    return caller.tenant_id if tenant_id == "me" else tenant_id


class TenantResponse(BaseModel):
    id: str
    name: str
    plan: str
    monthly_token_limit: int | None = None
    included_categories: list[str] | None = None
    prompt_gate_enabled: bool = False
    default_ocr_model: str = ""
    default_context_model: str = ""
    default_classification_model: str = ""
    default_summary_model: str = ""
    default_intent_model: str = ""
    created_at: str
    updated_at: str


def _to_response(t: Tenant) -> TenantResponse:
    return TenantResponse(
        id=t.id.value,
        name=t.name,
        plan=t.plan,
        monthly_token_limit=t.monthly_token_limit,
        included_categories=t.included_categories,
        prompt_gate_enabled=t.prompt_gate_enabled,
        default_ocr_model=t.default_ocr_model,
        default_context_model=t.default_context_model,
        default_classification_model=t.default_classification_model,
        default_summary_model=t.default_summary_model,
        default_intent_model=t.default_intent_model,
        created_at=t.created_at.isoformat(),
        updated_at=t.updated_at.isoformat(),
    )


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_tenant(
    body: CreateTenantRequest,
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: CreateTenantUseCase = Depends(
        Provide[Container.create_tenant_use_case]
    ),
) -> TenantResponse:
    try:
        tenant = await use_case.execute(
            CreateTenantCommand(name=body.name, plan=body.plan)
        )
    except DuplicateEntityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=e.message
        ) from None
    return _to_response(tenant)


@router.get("", response_model=PaginatedResponse[TenantResponse])
@inject
async def list_tenants(
    pagination: PaginationQuery = Depends(),
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListTenantsUseCase = Depends(
        Provide[Container.list_tenants_use_case]
    ),
    get_tenant_uc: GetTenantUseCase = Depends(
        Provide[Container.get_tenant_use_case]
    ),
) -> PaginatedResponse[TenantResponse]:
    limit = pagination.page_size
    offset = (pagination.page - 1) * pagination.page_size
    if tenant.role == "system_admin":
        tenants = await use_case.execute(limit=limit, offset=offset)
        total = await use_case.count()
    else:
        single = await get_tenant_uc.execute(tenant.tenant_id)
        tenants = [single]
        total = 1
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[_to_response(t) for t in tenants],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/{tenant_id}", response_model=TenantResponse)
@inject
async def get_tenant(
    tenant_id: str,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: GetTenantUseCase = Depends(
        Provide[Container.get_tenant_use_case]
    ),
) -> TenantResponse:
    try:
        tenant = await use_case.execute(tenant_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    return _to_response(tenant)


@router.patch("/{tenant_id}/config", response_model=TenantResponse)
@inject
async def update_tenant_config(
    tenant_id: str,
    body: UpdateTenantConfigRequest,
    actor: CurrentTenant = Depends(require_role("system_admin")),
    use_case: UpdateTenantUseCase = Depends(
        Provide[Container.update_tenant_use_case]
    ),
) -> TenantResponse:
    # Bug 2 修復：用 model_fields_set 區分「client 未傳」vs「client 顯式傳 None」。
    # 只把 client 顯式傳入的欄位放進 command，未傳者維持 _UNSET sentinel，
    # 讓 UpdateTenantUseCase 能正確保留 / 重置欄位。
    fields_set = body.model_fields_set
    cmd_kwargs: dict = {"tenant_id": tenant_id, "actor_user_id": actor.user_id}
    if "plan" in fields_set:
        cmd_kwargs["plan"] = body.plan
    if "monthly_token_limit" in fields_set:
        cmd_kwargs["monthly_token_limit"] = body.monthly_token_limit
    if "included_categories" in fields_set:
        cmd_kwargs["included_categories"] = body.included_categories  # 含顯式 null
    if "prompt_gate_enabled" in fields_set:
        cmd_kwargs["prompt_gate_enabled"] = body.prompt_gate_enabled
    if "default_ocr_model" in fields_set:
        cmd_kwargs["default_ocr_model"] = body.default_ocr_model
    if "default_context_model" in fields_set:
        cmd_kwargs["default_context_model"] = body.default_context_model
    if "default_classification_model" in fields_set:
        cmd_kwargs["default_classification_model"] = body.default_classification_model
    if "default_summary_model" in fields_set:
        cmd_kwargs["default_summary_model"] = body.default_summary_model
    if "default_intent_model" in fields_set:
        cmd_kwargs["default_intent_model"] = body.default_intent_model

    try:
        tenant = await use_case.execute(UpdateTenantCommand(**cmd_kwargs))
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    except DomainException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from None
    return _to_response(tenant)


@router.get("/{tenant_id}/quota", response_model=TenantQuotaResponse)
@inject
async def get_tenant_quota(
    tenant_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ComputeTenantQuotaUseCase = Depends(
        Provide[Container.compute_tenant_quota_use_case]
    ),
) -> TenantQuotaResponse:
    """回傳租戶本月額度狀態 — S-Ledger-Unification P5。

    所有數字從 token_usage_records + token_ledger_topups 即時算出，
    保證 base_total - base_remaining ≡ min(billable, base_total)（零 drift）。
    若本月 ledger 不存在會自動建立（從 plan + 上月 addon carryover）。
    """
    tenant_id = _resolve_tenant_alias(tenant_id, tenant)
    if tenant.role != "system_admin" and tenant.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other tenant's quota",
        )
    try:
        result = await use_case.execute(tenant_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    return TenantQuotaResponse(
        cycle_year_month=result.cycle_year_month,
        plan_name=result.plan_name,
        base_total=result.base_total,
        base_remaining=result.base_remaining,
        addon_remaining=result.addon_remaining,
        total_remaining=result.total_remaining,
        total_billable_in_cycle=result.total_billable_in_cycle,
        included_categories=result.included_categories,
        billing_mode=result.billing_mode,
        exhaustion_policy=result.exhaustion_policy,
        effective_policy=result.effective_policy,
        tenant_may_change_policy=result.tenant_may_change_policy,
        grace_percent=float(result.grace_percent),
        block_message=result.block_message,
        points_total=result.points_total,
        points_used=result.points_used,
        points_remaining=result.points_remaining,
    )


@router.put("/{tenant_id}/billing-policy", response_model=TenantBillingPolicyResponse)
@inject
async def update_tenant_billing_policy(
    tenant_id: str,
    body: UpdateTenantBillingPolicyRequest,
    caller: CurrentTenant = Depends(require_role("system_admin", "tenant_admin")),
    use_case: UpdateTenantBillingPolicyUseCase = Depends(
        Provide[Container.update_tenant_billing_policy_use_case]
    ),
) -> TenantBillingPolicyResponse:
    """Issue #74：額度用盡策略覆寫。tenant_admin 只能改自己且方案須允許（否則 403）。"""
    tenant_id = _resolve_tenant_alias(tenant_id, caller)
    if caller.role != "system_admin" and caller.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change other tenant's billing policy",
        )
    try:
        view = await use_case.execute(
            tenant_id=tenant_id,
            exhaustion_policy=body.exhaustion_policy,
            block_message=body.block_message,
            actor_role=caller.role,
            actor_user_id=caller.user_id,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from None
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message
        ) from None
    return TenantBillingPolicyResponse(
        tenant_id=view.tenant_id,
        exhaustion_policy_override=view.exhaustion_policy_override,
        block_message_override=view.block_message_override,
        effective_policy=view.effective_policy,
        block_message=view.block_message,
        tenant_may_change_policy=view.tenant_may_change_policy,
    )


@router.get(
    "/{tenant_id}/notification-preferences",
    response_model=TenantNotificationPreferencesResponse,
)
@inject
async def get_tenant_notification_preferences(
    tenant_id: str,
    caller: CurrentTenant = Depends(require_role("system_admin", "tenant_admin")),
    use_case: GetTenantNotificationPreferencesUseCase = Depends(
        Provide[Container.get_tenant_notification_preferences_use_case]
    ),
) -> TenantNotificationPreferencesResponse:
    """Issue #77：租戶設定變更通知偏好（`tenant_id` 可用 `me`；
    tenant_admin 只能讀自己）。"""
    tenant_id = _resolve_tenant_alias(tenant_id, caller)
    if caller.role != "system_admin" and caller.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot read other tenant's notification preferences",
        )
    try:
        view = await use_case.execute(tenant_id=tenant_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    return _preferences_response(view)


@router.put(
    "/{tenant_id}/notification-preferences",
    response_model=TenantNotificationPreferencesResponse,
)
@inject
async def update_tenant_notification_preferences(
    tenant_id: str,
    body: UpdateNotificationPreferencesRequest,
    caller: CurrentTenant = Depends(require_role("system_admin", "tenant_admin")),
    use_case: UpdateTenantNotificationPreferencesUseCase = Depends(
        Provide[Container.update_tenant_notification_preferences_use_case]
    ),
) -> TenantNotificationPreferencesResponse:
    """Issue #77：tenant_admin 只能改自己（他租戶 403）；未知群組 422；
    每次寫入留稽核。"""
    tenant_id = _resolve_tenant_alias(tenant_id, caller)
    try:
        view = await use_case.execute(
            tenant_id=tenant_id,
            groups=body.config_change_notify_fields,
            actor_role=caller.role,
            actor_tenant_id=caller.tenant_id,
            actor_user_id=caller.user_id,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from None
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message
        ) from None
    return _preferences_response(view)
