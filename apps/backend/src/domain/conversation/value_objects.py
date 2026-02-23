"""Conversation 限界上下文值物件"""

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class ConversationId:
    value: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class MessageId:
    value: str = field(default_factory=lambda: str(uuid4()))
