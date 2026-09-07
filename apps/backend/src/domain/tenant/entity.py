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
    # Issue #54 Phase C — 平台層 per-tenant 閘門功能開關（定案 5：system tenant seed 為 True）
    prompt_gate_enabled: bool = False
    default_ocr_model: str = ""
    default_context_model: str = ""
    default_classification_model: str = ""
    # S-KB-Followup.2: intent_classify / conversation_summary 的 tenant default
    default_summary_model: str = ""
    default_intent_model: str = ""
    # Issue #74：額度用盡策略 / 被擋文案覆寫（None = 沿用方案）
    exhaustion_policy_override: str | None = None
    block_message_override: str | None = None
    # Issue #77：設定變更通知的欄位群組（model / prompt / knowledge / tools / guard）
    # None = 平台預設（見 domain.observability.config_change.DEFAULT_NOTIFY_GROUPS）
    config_change_notify_fields: list[str] | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
