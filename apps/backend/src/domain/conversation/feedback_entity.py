"""Feedback 實體"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.conversation.feedback_value_objects import (
    Channel,
    FeedbackId,
    Rating,
)


@dataclass
class Feedback:
    id: FeedbackId
    tenant_id: str
    conversation_id: str
    message_id: str
    user_id: str | None
    channel: Channel
    rating: Rating
    comment: str | None
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
