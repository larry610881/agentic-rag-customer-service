from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


@dataclass(frozen=True)
class RateLimitConfigId:
    value: str = field(default_factory=lambda: str(uuid4()))


class EndpointGroup(StrEnum):
    FEEDBACK = "feedback"
    RAG = "rag"
    GENERAL = "general"
    WEBHOOK = "webhook"
