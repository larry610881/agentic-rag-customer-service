"""回饋 API 端點"""

from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.application.conversation.get_feedback_stats_use_case import (
    GetFeedbackStatsUseCase,
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
