"""GetConversationMessagesUseCase — 單 conversation 訊息查詢

S-ConvInsights.1：admin「對話與追蹤」頁 訊息 tab 用。
reuse 既有 `ConversationRepository.find_by_id()`（已一併回訊息 list）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.conversation.repository import ConversationRepository
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass
class GetConversationMessagesQuery:
    conversation_id: str
    # auth context
    role: str  # "system_admin" | "tenant_admin"
    tenant_id: str  # JWT tenant_id（tenant_admin 必須與 conversation 的 tenant 相同）


@dataclass
class ConversationMessagesResult:
    conversation_id: str
    tenant_id: str
    bot_id: str | None
    created_at: str | None
    summary: str | None
    message_count: int
    last_message_at: str | None
    messages: list[dict[str, Any]] = field(default_factory=list)


class GetConversationMessagesUseCase:
    def __init__(self, conversation_repo: ConversationRepository) -> None:
        self._repo = conversation_repo

    async def execute(
        self, query: GetConversationMessagesQuery
    ) -> ConversationMessagesResult:
        conv = await self._repo.find_by_id(query.conversation_id)
        if conv is None:
            raise EntityNotFoundError(
                entity_type="Conversation",
                entity_id=query.conversation_id,
            )

        # Tenant isolation: tenant_admin 只能看自己租戶
        if query.role != "system_admin" and conv.tenant_id != query.tenant_id:
            raise EntityNotFoundError(
                entity_type="Conversation",
                entity_id=query.conversation_id,
            )

        messages = [
            {
                "message_id": m.id.value,
                "role": m.role,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "latency_ms": m.latency_ms,
                "retrieved_chunks": m.retrieved_chunks,
                "structured_content": m.structured_content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in conv.messages
        ]

        return ConversationMessagesResult(
            conversation_id=conv.id.value,
            tenant_id=conv.tenant_id,
            bot_id=conv.bot_id,
            created_at=conv.created_at.isoformat() if conv.created_at else None,
            summary=conv.summary,
            message_count=conv.message_count,
            last_message_at=(
                conv.last_message_at.isoformat() if conv.last_message_at else None
            ),
            messages=messages,
        )
