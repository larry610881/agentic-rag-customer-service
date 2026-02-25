"""對話歷史查詢 API 端點"""

from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.application.conversation.get_conversation_use_case import (
    GetConversationUseCase,
)
from src.application.conversation.list_conversations_use_case import (
    ListConversationsUseCase,
)
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversations"],
)


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    id: str
    tenant_id: str
    bot_id: str | None = None
    messages: list[MessageResponse]
    created_at: datetime


class ConversationSummaryResponse(BaseModel):
    id: str
    tenant_id: str
    bot_id: str | None = None
    created_at: datetime


@router.get("", response_model=list[ConversationSummaryResponse])
@inject
async def list_conversations(
    bot_id: str | None = None,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListConversationsUseCase = Depends(
        Provide[Container.list_conversations_use_case]
    ),
) -> list[ConversationSummaryResponse]:
    conversations = await use_case.execute(
        tenant_id=tenant.tenant_id, bot_id=bot_id
    )
    return [
        ConversationSummaryResponse(
            id=c.id.value,
            tenant_id=c.tenant_id,
            bot_id=c.bot_id,
            created_at=c.created_at,
        )
        for c in conversations
    ]


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
@inject
async def get_conversation(
    conversation_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: GetConversationUseCase = Depends(
        Provide[Container.get_conversation_use_case]
    ),
) -> ConversationDetailResponse:
    conversation = await use_case.execute(conversation_id=conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.tenant_id != tenant.tenant_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetailResponse(
        id=conversation.id.value,
        tenant_id=conversation.tenant_id,
        bot_id=conversation.bot_id,
        messages=[
            MessageResponse(
                id=m.id.value,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in conversation.messages
        ],
        created_at=conversation.created_at,
    )
