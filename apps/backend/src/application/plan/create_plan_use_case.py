"""Create Plan Use Case — S-Token-Gov.1（Issue #74：計價模式 / 用盡策略 + 稽核）"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from src.application.plan.update_plan_use_case import plan_audit_view
from src.domain.plan.entity import BillingMode, ExhaustionPolicy, Plan
from src.domain.plan.repository import PlanRepository
from src.domain.shared.exceptions import DomainException


@dataclass(frozen=True)
class CreatePlanCommand:
    name: str
    base_monthly_tokens: int
    addon_pack_tokens: int
    base_price: Decimal
    addon_price: Decimal
    currency: str = "TWD"
    description: str | None = None
    is_active: bool = True
    # Issue #74
    billing_mode: str = BillingMode.TOKEN
    monthly_points: int = 0
    addon_pack_points: int = 0
    default_category_multiplier: Decimal = Decimal("1")
    exhaustion_policy: str = ExhaustionPolicy.AUTO_TOPUP
    tenant_may_change_policy: bool = False
    auto_topup_monthly_cap: int = 0
    grace_percent: Decimal = Decimal("0")
    block_message: str = ""
    actor_user_id: str | None = None


class CreatePlanUseCase:
    def __init__(
        self, plan_repository: PlanRepository, audit: Any | None = None
    ) -> None:
        self._repo = plan_repository
        self._audit = audit

    async def execute(self, command: CreatePlanCommand) -> Plan:
        if not command.name.strip():
            raise DomainException("Plan name is required")
        # 唯一性檢查
        existing = await self._repo.find_by_name(command.name)
        if existing is not None:
            raise DomainException(
                f"Plan with name '{command.name}' already exists"
            )
        if command.base_monthly_tokens < 0 or command.addon_pack_tokens < 0:
            raise DomainException("Token counts must be >= 0")
        if command.base_price < 0 or command.addon_price < 0:
            raise DomainException("Prices must be >= 0")

        plan = Plan(
            name=command.name,
            base_monthly_tokens=command.base_monthly_tokens,
            addon_pack_tokens=command.addon_pack_tokens,
            base_price=command.base_price,
            addon_price=command.addon_price,
            currency=command.currency,
            description=command.description,
            is_active=command.is_active,
            billing_mode=command.billing_mode,
            monthly_points=command.monthly_points,
            addon_pack_points=command.addon_pack_points,
            default_category_multiplier=Decimal(command.default_category_multiplier),
            exhaustion_policy=command.exhaustion_policy,
            tenant_may_change_policy=command.tenant_may_change_policy,
            auto_topup_monthly_cap=command.auto_topup_monthly_cap,
            grace_percent=Decimal(command.grace_percent),
            block_message=command.block_message.strip(),
        )
        plan.validate_billing()
        saved = await self._repo.save(plan)
        if self._audit is not None:
            await self._audit.record(
                entity_type="plan", entity_id=plan.id, action="create",
                before=None, after=plan_audit_view(plan),
                actor_user_id=command.actor_user_id,
            )
        return saved
