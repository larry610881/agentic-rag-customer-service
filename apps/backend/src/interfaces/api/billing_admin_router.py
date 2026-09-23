"""Admin Billing Settings Router — Issue #74（system_admin only）

平台點數匯率：1 點 = `usd_per_point` USD（模型未設點數表時的換算依據）。
"""

from __future__ import annotations

from decimal import Decimal

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.application.billing.billing_settings_use_cases import (
    GetBillingSettingsUseCase,
    UpdateBillingSettingsUseCase,
)
from src.container import Container
from src.domain.billing.settings import BillingSettings
from src.domain.shared.exceptions import ValidationError
from src.interfaces.api.deps import CurrentTenant, require_role
from src.interfaces.api.errors import ApiError
from src.interfaces.api.types import ApiDateTime

router = APIRouter(prefix="/api/v1/admin/billing", tags=["admin-billing"])


class BillingSettingsResponse(BaseModel):
    usd_per_point: Decimal
    updated_by: str | None = None
    updated_at: ApiDateTime


class UpdateBillingSettingsRequest(BaseModel):
    usd_per_point: Decimal = Field(..., gt=0)


def _to_response(s: BillingSettings) -> BillingSettingsResponse:
    return BillingSettingsResponse(
        usd_per_point=s.usd_per_point,
        updated_by=s.updated_by,
        updated_at=s.updated_at,
    )


@router.get("/settings", response_model=BillingSettingsResponse)
@inject
async def get_billing_settings(
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: GetBillingSettingsUseCase = Depends(
        Provide[Container.get_billing_settings_use_case]
    ),
) -> BillingSettingsResponse:
    return _to_response(await use_case.execute())


@router.put("/settings", response_model=BillingSettingsResponse)
@inject
async def update_billing_settings(
    body: UpdateBillingSettingsRequest,
    admin: CurrentTenant = Depends(require_role("system_admin")),
    use_case: UpdateBillingSettingsUseCase = Depends(
        Provide[Container.update_billing_settings_use_case]
    ),
) -> BillingSettingsResponse:
    try:
        settings = await use_case.execute(
            usd_per_point=body.usd_per_point, actor_user_id=admin.user_id
        )
    except ValidationError as e:
        raise ApiError(
            422,
            code="invalid_request",
            message=e.message,
        ) from None
    return _to_response(settings)
