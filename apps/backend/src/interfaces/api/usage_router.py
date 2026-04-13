"""Token Usage 查詢 API 端點"""

from datetime import date, datetime, timedelta, timezone

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.application.usage.query_bot_usage_use_case import QueryBotUsageUseCase
from src.application.usage.query_daily_usage_use_case import QueryDailyUsageUseCase
from src.application.usage.query_monthly_usage_use_case import QueryMonthlyUsageUseCase
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


class BotUsageStatResponse(BaseModel):
    bot_id: str | None
    bot_name: str | None
    model: str
    request_type: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    message_count: int


class DailyUsageStatResponse(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    message_count: int


@router.get("/by-bot", response_model=list[BotUsageStatResponse])
@inject
async def get_usage_by_bot(
    start_date: date | None = None,
    end_date: date | None = None,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: QueryBotUsageUseCase = Depends(
        Provide[Container.query_bot_usage_use_case]
    ),
) -> list[BotUsageStatResponse]:
    if start_date is None and end_date is None:
        dt_end = datetime.now(timezone.utc)
        dt_start = dt_end - timedelta(days=30)
    else:
        dt_start = (
            datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
            if start_date
            else None
        )
        dt_end = (
            datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
            if end_date
            else None
        )
    stats = await use_case.execute(tenant.tenant_id, dt_start, dt_end)
    return [
        BotUsageStatResponse(
            bot_id=s.bot_id,
            bot_name=s.bot_name,
            model=s.model,
            request_type=s.request_type,
            input_tokens=s.input_tokens,
            output_tokens=s.output_tokens,
            total_tokens=s.total_tokens,
            estimated_cost=s.estimated_cost,
            message_count=s.message_count,
        )
        for s in stats
    ]


@router.get("/daily", response_model=list[DailyUsageStatResponse])
@inject
async def get_daily_usage(
    start_date: date | None = None,
    end_date: date | None = None,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: QueryDailyUsageUseCase = Depends(
        Provide[Container.query_daily_usage_use_case]
    ),
) -> list[DailyUsageStatResponse]:
    if start_date is None and end_date is None:
        dt_end = datetime.now(timezone.utc)
        dt_start = dt_end - timedelta(days=30)
    else:
        dt_start = (
            datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
            if start_date
            else None
        )
        dt_end = (
            datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
            if end_date
            else None
        )
    stats = await use_case.execute(tenant.tenant_id, dt_start, dt_end)
    return [
        DailyUsageStatResponse(
            date=s.date,
            input_tokens=s.input_tokens,
            output_tokens=s.output_tokens,
            total_tokens=s.total_tokens,
            estimated_cost=s.estimated_cost,
            message_count=s.message_count,
        )
        for s in stats
    ]


class MonthlyUsageStatResponse(BaseModel):
    month: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    message_count: int


@router.get("/monthly", response_model=list[MonthlyUsageStatResponse])
@inject
async def get_monthly_usage(
    start_date: date | None = None,
    end_date: date | None = None,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: QueryMonthlyUsageUseCase = Depends(
        Provide[Container.query_monthly_usage_use_case]
    ),
) -> list[MonthlyUsageStatResponse]:
    if start_date is None and end_date is None:
        dt_end = datetime.now(timezone.utc)
        dt_start = dt_end - timedelta(days=365)
    else:
        dt_start = (
            datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
            if start_date
            else None
        )
        dt_end = (
            datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
            if end_date
            else None
        )
    stats = await use_case.execute(tenant.tenant_id, dt_start, dt_end)
    return [
        MonthlyUsageStatResponse(
            month=s.month,
            input_tokens=s.input_tokens,
            output_tokens=s.output_tokens,
            total_tokens=s.total_tokens,
            estimated_cost=s.estimated_cost,
            message_count=s.message_count,
        )
        for s in stats
    ]
