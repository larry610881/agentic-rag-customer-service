"""Admin Conversation Insights Router — S-ConvInsights.1

合併「對話搜尋 + 可觀測性 + 對話摘要」的 composite endpoints，
供新頁 /admin/conversations（master-detail）右側 tabs 用。

- GET /api/v1/admin/conversations/{cid}/messages       — 訊息 tab
- GET /api/v1/admin/conversations/{cid}/token-usage    — Token 用量 tab

Trace tab 直接用既有 /api/v1/observability/agent-traces?conversation_id=...
Summary tab 用 left list 回傳的 summary 欄位（無需新 endpoint）
"""

from __future__ import annotations

import logging
from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.conversation.get_conversation_messages_use_case import (
    GetConversationMessagesQuery,
    GetConversationMessagesUseCase,
)
from src.application.conversation.get_conversation_token_usage_use_case import (
    GetConversationTokenUsageQuery,
    GetConversationTokenUsageUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, require_role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin/conversations", tags=["admin-conversation-insights"]
)


class MessageItem(BaseModel):
    message_id: str
    role: str
    content: str
    tool_calls: list[dict[str, Any]] = []
    latency_ms: int | None = None
    retrieved_chunks: list[dict[str, Any]] | None = None
    structured_content: dict[str, Any] | None = None
    created_at: str | None = None


class ConversationMessagesResponse(BaseModel):
    conversation_id: str
    tenant_id: str
    bot_id: str | None = None
    created_at: str | None = None
    summary: str | None = None
    message_count: int = 0
    last_message_at: str | None = None
    messages: list[MessageItem]


class TokenUsageRow(BaseModel):
    """Sprint A+ Bug 1: 加 bot_name + channel_source 讓前端顯示兩階來源。"""

    model: str
    request_type: str
    kb_id: str | None = None
    kb_name: str | None = None
    bot_id: str | None = None
    bot_name: str | None = None
    channel_source: str | None = None  # "web" | "widget" | "line" | "studio" | ""
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    estimated_cost: float
    message_count: int


class TokenUsageTotals(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    estimated_cost: float
    message_count: int


class ConversationTokenUsageResponse(BaseModel):
    conversation_id: str
    totals: TokenUsageTotals
    by_request_type: list[TokenUsageRow]


@router.get("/{conversation_id}/messages", response_model=ConversationMessagesResponse)
@inject
async def get_conversation_messages(
    conversation_id: str,
    admin: CurrentTenant = Depends(require_role("system_admin", "tenant_admin")),
    use_case: GetConversationMessagesUseCase = Depends(
        Provide[Container.get_conversation_messages_use_case]
    ),
) -> ConversationMessagesResponse:
    try:
        result = await use_case.execute(
            GetConversationMessagesQuery(
                conversation_id=conversation_id,
                role=admin.role or "tenant_admin",
                tenant_id=admin.tenant_id or "",
            )
        )
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        ) from exc

    return ConversationMessagesResponse(
        conversation_id=result.conversation_id,
        tenant_id=result.tenant_id,
        bot_id=result.bot_id,
        created_at=result.created_at,
        summary=result.summary,
        message_count=result.message_count,
        last_message_at=result.last_message_at,
        messages=[MessageItem(**m) for m in result.messages],
    )


@router.get(
    "/{conversation_id}/token-usage",
    response_model=ConversationTokenUsageResponse,
)
@inject
async def get_conversation_token_usage(
    conversation_id: str,
    admin: CurrentTenant = Depends(require_role("system_admin", "tenant_admin")),
    use_case: GetConversationTokenUsageUseCase = Depends(
        Provide[Container.get_conversation_token_usage_use_case]
    ),
) -> ConversationTokenUsageResponse:
    try:
        result = await use_case.execute(
            GetConversationTokenUsageQuery(
                conversation_id=conversation_id,
                role=admin.role or "tenant_admin",
                tenant_id=admin.tenant_id or "",
            )
        )
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        ) from exc

    return ConversationTokenUsageResponse(
        conversation_id=result.conversation_id,
        totals=TokenUsageTotals(
            input_tokens=result.totals.input_tokens,
            output_tokens=result.totals.output_tokens,
            cache_read_tokens=result.totals.cache_read_tokens,
            cache_creation_tokens=result.totals.cache_creation_tokens,
            estimated_cost=result.totals.estimated_cost,
            message_count=result.totals.message_count,
        ),
        by_request_type=[TokenUsageRow(**r) for r in result.by_request_type],
    )
