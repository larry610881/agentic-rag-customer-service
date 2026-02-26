from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.ratelimit.value_objects import EndpointGroup, RateLimitConfigId


@dataclass
class RateLimitConfig:
    id: RateLimitConfigId = field(default_factory=RateLimitConfigId)
    tenant_id: str | None = None  # None = global default
    endpoint_group: EndpointGroup = EndpointGroup.GENERAL
    requests_per_minute: int = 200
    burst_size: int = 250
    per_user_requests_per_minute: int | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
