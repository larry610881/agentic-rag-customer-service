"""Conversation 限界上下文實體"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.domain.conversation.value_objects import ConversationId, MessageId


@dataclass
class Message:
    id: MessageId
    conversation_id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class Conversation:
    id: ConversationId = field(default_factory=ConversationId)
    tenant_id: str = ""
    bot_id: str | None = None
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> Message:
        message = Message(
            id=MessageId(),
            conversation_id=self.id.value,
            role=role,
            content=content,
            tool_calls=tool_calls or [],
        )
        self.messages.append(message)
        return message
