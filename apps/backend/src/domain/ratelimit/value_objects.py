from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


@dataclass(frozen=True)
class RateLimitConfigId:
    value: str = field(default_factory=lambda: str(uuid4()))


class EndpointGroup(StrEnum):
    AUTH = "auth"  # Issue #58：login / register / token，per-IP 節流
    FEEDBACK = "feedback"
    RAG = "rag"
    GENERAL = "general"
    WEBHOOK = "webhook"
