from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.tenant.value_objects import TenantId


@dataclass
class Tenant:
    id: TenantId = field(default_factory=TenantId)
    name: str = ""
    plan: str = "starter"
    monthly_token_limit: int | None = None
    # S-Token-Gov.2: 哪些 UsageCategory 計入額度。
    # None → 全計入（safe default）；[] → 全不計入（POC 免計費）；list → 只計入列表內的
    included_categories: list[str] | None = None
    default_ocr_model: str = ""
    default_context_model: str = ""
    default_classification_model: str = ""
    # S-KB-Followup.2: intent_classify / conversation_summary 的 tenant default
    default_summary_model: str = ""
    default_intent_model: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
