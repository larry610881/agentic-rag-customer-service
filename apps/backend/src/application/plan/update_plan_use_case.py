"""Update Plan Use Case — S-Token-Gov.1

不允許改 name（要改就刪除重建）；其他欄位可改。
Issue #74：加計價模式 / 點數 / 用盡策略欄位；變更寫稽核（entity_type plan）
並清計價快取。
切換方案只影響之後的用量，不重算歷史 usage_records.points。
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from src.domain.plan.entity import Plan
from src.domain.plan.repository import PlanRepository
from src.domain.shared.exceptions import DomainException, EntityNotFoundError

PLAN_AUDIT_FIELDS: tuple[str, ...] = (
    "name", "base_monthly_tokens", "addon_pack_tokens", "base_price", "addon_price",
    "currency", "description", "is_active", "billing_mode", "monthly_points",
    "addon_pack_points", "default_category_multiplier", "exhaustion_policy",
    "tenant_may_change_policy", "auto_topup_monthly_cap", "grace_percent",
    "block_message",
)


def plan_audit_view(plan: Plan) -> dict[str, Any]:
    view: dict[str, Any] = {}
    for f in PLAN_AUDIT_FIELDS:
        value = getattr(plan, f, None)
        view[f] = str(value) if isinstance(value, Decimal) else value
    return view


@dataclass(frozen=True)
class UpdatePlanCommand:
    plan_id: str
    base_monthly_tokens: int | None = None
    addon_pack_tokens: int | None = None
    base_price: Decimal | None = None
    addon_price: Decimal | None = None
    currency: str | None = None
    description: str | None = None
    is_active: bool | None = None
    # Issue #74
    billing_mode: str | None = None
    monthly_points: int | None = None
    addon_pack_points: int | None = None
    default_category_multiplier: Decimal | None = None
    exhaustion_policy: str | None = None
    tenant_may_change_policy: bool | None = None
    auto_topup_monthly_cap: int | None = None
    grace_percent: Decimal | None = None
    block_message: str | None = None
    actor_user_id: str | None = None


class UpdatePlanUseCase:
    def __init__(
        self,
        plan_repository: PlanRepository,
        audit: Any | None = None,
        billing_context: Any | None = None,
    ) -> None:
        self._repo = plan_repository
        self._audit = audit
        self._billing_context = billing_context

    async def execute(self, command: UpdatePlanCommand) -> Plan:  # noqa: C901
        plan = await self._repo.find_by_id(command.plan_id)
        if plan is None:
            raise EntityNotFoundError("Plan", command.plan_id)
        before = plan_audit_view(plan)

        if command.base_monthly_tokens is not None:
            if command.base_monthly_tokens < 0:
                raise DomainException("base_monthly_tokens must be >= 0")
            plan.base_monthly_tokens = command.base_monthly_tokens
        if command.addon_pack_tokens is not None:
            if command.addon_pack_tokens < 0:
                raise DomainException("addon_pack_tokens must be >= 0")
            plan.addon_pack_tokens = command.addon_pack_tokens
        if command.base_price is not None:
            if command.base_price < 0:
                raise DomainException("base_price must be >= 0")
            plan.base_price = command.base_price
        if command.addon_price is not None:
            if command.addon_price < 0:
                raise DomainException("addon_price must be >= 0")
            plan.addon_price = command.addon_price
        if command.currency is not None:
            plan.currency = command.currency
        if command.description is not None:
            plan.description = command.description
        if command.is_active is not None:
            plan.is_active = command.is_active

        # Issue #74
        if command.billing_mode is not None:
            plan.billing_mode = command.billing_mode
        if command.monthly_points is not None:
            plan.monthly_points = command.monthly_points
        if command.addon_pack_points is not None:
            plan.addon_pack_points = command.addon_pack_points
        if command.default_category_multiplier is not None:
            plan.default_category_multiplier = Decimal(
                command.default_category_multiplier
            )
        if command.exhaustion_policy is not None:
            plan.exhaustion_policy = command.exhaustion_policy
        if command.tenant_may_change_policy is not None:
            plan.tenant_may_change_policy = bool(command.tenant_may_change_policy)
        if command.auto_topup_monthly_cap is not None:
            plan.auto_topup_monthly_cap = command.auto_topup_monthly_cap
        if command.grace_percent is not None:
            plan.grace_percent = Decimal(command.grace_percent)
        if command.block_message is not None:
            plan.block_message = command.block_message.strip()
        plan.validate_billing()

        saved = await self._repo.save(plan)
        if self._billing_context is not None:
            self._billing_context.invalidate(None)
        if self._audit is not None:
            await self._audit.record(
                entity_type="plan", entity_id=plan.id, action="update",
                before=before, after=plan_audit_view(plan),
                actor_user_id=command.actor_user_id,
            )
        return saved
