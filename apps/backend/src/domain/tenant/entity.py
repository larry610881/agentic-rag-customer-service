from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.tenant.value_objects import TenantId


@dataclass
class Tenant:
    id: TenantId = field(default_factory=TenantId)
    name: str = ""
    plan: str = "starter"
    monthly_token_limit: int | None = None
    default_ocr_model: str = ""
    default_context_model: str = ""
    default_classification_model: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
