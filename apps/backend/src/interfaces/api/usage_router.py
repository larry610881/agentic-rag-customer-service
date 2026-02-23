"""Token Usage 查詢 API 端點"""

from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.application.usage.query_usage_use_case import QueryUsageUseCase
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(
    prefix="/api/v1/usage",
    tags=["usage"],
)


class UsageSummaryResponse(BaseModel):
    tenant_id: str
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost: float
    by_model: dict[str, int]
    by_request_type: dict[str, int]


@router.get("", response_model=UsageSummaryResponse)
@inject
async def get_usage_summary(
    tenant: CurrentTenant = Depends(get_current_tenant),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    use_case: QueryUsageUseCase = Depends(
        Provide[Container.query_usage_use_case]
    ),
) -> UsageSummaryResponse:
    summary = await use_case.execute(
        tenant_id=tenant.tenant_id,
        start_date=start_date,
        end_date=end_date,
    )
    return UsageSummaryResponse(
        tenant_id=summary.tenant_id,
        total_input_tokens=summary.total_input_tokens,
        total_output_tokens=summary.total_output_tokens,
        total_tokens=summary.total_tokens,
        total_cost=summary.total_cost,
        by_model=summary.by_model,
        by_request_type=summary.by_request_type,
    )
