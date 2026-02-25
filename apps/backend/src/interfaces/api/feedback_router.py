"""回饋 API 端點"""

import csv
import io
import json
from datetime import date, datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.application.conversation.get_feedback_stats_use_case import (
    GetFeedbackStatsUseCase,
)
from src.application.conversation.get_retrieval_quality_use_case import (
    GetRetrievalQualityUseCase,
)
from src.application.conversation.get_satisfaction_trend_use_case import (
    GetSatisfactionTrendUseCase,
)
from src.application.conversation.get_token_cost_stats_use_case import (
    GetTokenCostStatsUseCase,
)
from src.application.conversation.get_top_issues_use_case import (
    GetTopIssuesUseCase,
)
from src.application.conversation.list_feedback_use_case import (
    ListFeedbackUseCase,
)
from src.application.conversation.submit_feedback_use_case import (
    SubmitFeedbackCommand,
    SubmitFeedbackUseCase,
)
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(
    prefix="/api/v1/feedback",
    tags=["feedback"],
)


class SubmitFeedbackRequest(BaseModel):
    conversation_id: str
    message_id: str
    channel: str = "web"
    rating: str
    user_id: str | None = None
    comment: str | None = None
    tags: list[str] = []


class FeedbackResponse(BaseModel):
    id: str
    tenant_id: str
    conversation_id: str
    message_id: str
    user_id: str | None
    channel: str
    rating: str
    comment: str | None
    tags: list[str]
    created_at: datetime


class FeedbackStatsResponse(BaseModel):
    total: int
    thumbs_up: int
    thumbs_down: int
    satisfaction_rate: float


class UpdateTagsRequest(BaseModel):
    tags: list[str]


class DailyFeedbackStatResponse(BaseModel):
    date: date
    total: int
    positive: int
    negative: int
    satisfaction_pct: float


class TagCountResponse(BaseModel):
    tag: str
    count: int


class RetrievalQualityResponse(BaseModel):
    user_question: str
    assistant_answer: str
    retrieved_chunks: list[dict]
    rating: str
    comment: str | None
    created_at: datetime


class ModelCostStatResponse(BaseModel):
    model: str
    message_count: int
    input_tokens: int
    output_tokens: int
    avg_latency_ms: float
    estimated_cost: float


class DataRetentionResponse(BaseModel):
    purged_count: int


@router.post("", response_model=FeedbackResponse, status_code=201)
@inject
async def submit_feedback(
    body: SubmitFeedbackRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: SubmitFeedbackUseCase = Depends(
        Provide[Container.submit_feedback_use_case]
    ),
) -> FeedbackResponse:
    command = SubmitFeedbackCommand(
        tenant_id=tenant.tenant_id,
        conversation_id=body.conversation_id,
        message_id=body.message_id,
        channel=body.channel,
        rating=body.rating,
        user_id=body.user_id,
        comment=body.comment,
        tags=body.tags,
    )
    feedback = await use_case.execute(command)
    return FeedbackResponse(
        id=feedback.id.value,
        tenant_id=feedback.tenant_id,
        conversation_id=feedback.conversation_id,
        message_id=feedback.message_id,
        user_id=feedback.user_id,
        channel=feedback.channel.value,
        rating=feedback.rating.value,
        comment=feedback.comment,
        tags=feedback.tags,
        created_at=feedback.created_at,
    )


@router.get("", response_model=list[FeedbackResponse])
@inject
async def list_feedback(
    limit: int = 50,
    offset: int = 0,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListFeedbackUseCase = Depends(
        Provide[Container.list_feedback_use_case]
    ),
) -> list[FeedbackResponse]:
    feedbacks = await use_case.execute(
        tenant.tenant_id, limit=limit, offset=offset
    )
    return [
        FeedbackResponse(
            id=f.id.value,
            tenant_id=f.tenant_id,
            conversation_id=f.conversation_id,
            message_id=f.message_id,
            user_id=f.user_id,
            channel=f.channel.value,
            rating=f.rating.value,
            comment=f.comment,
            tags=f.tags,
            created_at=f.created_at,
        )
        for f in feedbacks
    ]


@router.get("/stats", response_model=FeedbackStatsResponse)
@inject
async def get_feedback_stats(
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetFeedbackStatsUseCase = Depends(
        Provide[Container.get_feedback_stats_use_case]
    ),
) -> FeedbackStatsResponse:
    stats = await use_case.execute(tenant.tenant_id)
    return FeedbackStatsResponse(
        total=stats.total,
        thumbs_up=stats.thumbs_up,
        thumbs_down=stats.thumbs_down,
        satisfaction_rate=stats.satisfaction_rate,
    )


@router.get(
    "/conversation/{conversation_id}",
    response_model=list[FeedbackResponse],
)
@inject
async def get_conversation_feedback(
    conversation_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListFeedbackUseCase = Depends(
        Provide[Container.list_feedback_use_case]
    ),
) -> list[FeedbackResponse]:
    feedbacks = await use_case.execute_by_conversation(
        conversation_id, tenant.tenant_id
    )
    return [
        FeedbackResponse(
            id=f.id.value,
            tenant_id=f.tenant_id,
            conversation_id=f.conversation_id,
            message_id=f.message_id,
            user_id=f.user_id,
            channel=f.channel.value,
            rating=f.rating.value,
            comment=f.comment,
            tags=f.tags,
            created_at=f.created_at,
        )
        for f in feedbacks
    ]


@router.patch("/{feedback_id}/tags")
@inject
async def update_feedback_tags(
    feedback_id: str,
    body: UpdateTagsRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListFeedbackUseCase = Depends(
        Provide[Container.list_feedback_use_case]
    ),
) -> dict:
    await use_case.update_tags(feedback_id, body.tags)
    return {"status": "ok"}


# --- Analysis Endpoints ---


@router.get(
    "/analysis/satisfaction-trend",
    response_model=list[DailyFeedbackStatResponse],
)
@inject
async def get_satisfaction_trend(
    days: int = 30,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetSatisfactionTrendUseCase = Depends(
        Provide[Container.get_satisfaction_trend_use_case]
    ),
) -> list[DailyFeedbackStatResponse]:
    stats = await use_case.execute(tenant.tenant_id, days)
    return [
        DailyFeedbackStatResponse(
            date=s.date,
            total=s.total,
            positive=s.positive,
            negative=s.negative,
            satisfaction_pct=s.satisfaction_pct,
        )
        for s in stats
    ]


@router.get(
    "/analysis/top-issues",
    response_model=list[TagCountResponse],
)
@inject
async def get_top_issues(
    days: int = 30,
    limit: int = 10,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetTopIssuesUseCase = Depends(
        Provide[Container.get_top_issues_use_case]
    ),
) -> list[TagCountResponse]:
    tags = await use_case.execute(tenant.tenant_id, days, limit)
    return [TagCountResponse(tag=t.tag, count=t.count) for t in tags]


@router.get(
    "/analysis/retrieval-quality",
    response_model=list[RetrievalQualityResponse],
)
@inject
async def get_retrieval_quality(
    days: int = 30,
    limit: int = 20,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetRetrievalQualityUseCase = Depends(
        Provide[Container.get_retrieval_quality_use_case]
    ),
) -> list[RetrievalQualityResponse]:
    records = await use_case.execute(tenant.tenant_id, days, limit)
    return [
        RetrievalQualityResponse(
            user_question=r.user_question,
            assistant_answer=r.assistant_answer,
            retrieved_chunks=r.retrieved_chunks,
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get(
    "/analysis/token-cost",
    response_model=list[ModelCostStatResponse],
)
@inject
async def get_token_cost(
    days: int = 30,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetTokenCostStatsUseCase = Depends(
        Provide[Container.get_token_cost_stats_use_case]
    ),
) -> list[ModelCostStatResponse]:
    stats = await use_case.execute(tenant.tenant_id, days)
    return [
        ModelCostStatResponse(
            model=s.model,
            message_count=s.message_count,
            input_tokens=s.input_tokens,
            output_tokens=s.output_tokens,
            avg_latency_ms=s.avg_latency_ms,
            estimated_cost=s.estimated_cost,
        )
        for s in stats
    ]


# --- Enterprise Data Management Endpoints ---


@router.get("/export")
@inject
async def export_feedback(
    format: str = "json",
    days: int = 90,
    mask_pii: bool = False,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListFeedbackUseCase = Depends(
        Provide[Container.list_feedback_use_case]
    ),
) -> StreamingResponse:
    from src.application.conversation.export_feedback_use_case import (
        ExportFeedbackUseCase,
    )

    export_uc = ExportFeedbackUseCase(use_case._feedback_repo)
    content = await export_uc.execute(
        tenant.tenant_id, format=format, days=days, mask_pii=mask_pii
    )

    if format == "csv":
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=feedback.csv"},
        )
    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=feedback.json"},
    )


@router.delete("/retention", response_model=DataRetentionResponse)
@inject
async def delete_old_feedback(
    months: int = 6,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListFeedbackUseCase = Depends(
        Provide[Container.list_feedback_use_case]
    ),
) -> DataRetentionResponse:
    from src.application.conversation.data_retention_use_case import (
        DataRetentionUseCase,
    )

    retention_uc = DataRetentionUseCase(use_case._feedback_repo)
    count = await retention_uc.execute(tenant.tenant_id, months=months)
    return DataRetentionResponse(purged_count=count)
