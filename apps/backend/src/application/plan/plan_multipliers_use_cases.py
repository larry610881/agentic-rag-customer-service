"""方案類別倍率用例（僅 system_admin）— Issue #74"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from src.domain.plan.multiplier_repository import PlanCategoryMultiplierRepository
from src.domain.plan.repository import PlanRepository
from src.domain.plan.value_objects import PlanCategoryMultiplier
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError
from src.domain.usage.category import DEPRECATED_CATEGORIES, UsageCategory

_VALID_CATEGORIES: frozenset[str] = frozenset(
    c.value for c in UsageCategory if c.value not in DEPRECATED_CATEGORIES
)


@dataclass(frozen=True)
class PlanMultipliersView:
    plan_id: str
    default_category_multiplier: Decimal
    multipliers: dict[str, Decimal]


class GetPlanMultipliersUseCase:
    def __init__(
        self,
        plan_repository: PlanRepository,
        multiplier_repository: PlanCategoryMultiplierRepository,
    ) -> None:
        self._plan_repo = plan_repository
        self._repo = multiplier_repository

    async def execute(self, plan_id: str) -> PlanMultipliersView:
        plan = await self._plan_repo.find_by_id(plan_id)
        if plan is None:
            raise EntityNotFoundError("Plan", plan_id)
        rows = await self._repo.list_for_plan(plan_id)
        return PlanMultipliersView(
            plan_id=plan_id,
            default_category_multiplier=plan.default_category_multiplier,
            multipliers={r.usage_category: r.multiplier for r in rows},
        )


class ReplacePlanMultipliersUseCase:
    def __init__(
        self,
        plan_repository: PlanRepository,
        multiplier_repository: PlanCategoryMultiplierRepository,
        billing_context: Any | None = None,
        audit: Any | None = None,
    ) -> None:
        self._plan_repo = plan_repository
        self._repo = multiplier_repository
        self._billing_context = billing_context
        self._audit = audit

    async def execute(
        self,
        *,
        plan_id: str,
        multipliers: dict[str, Any],
        actor_user_id: str | None,
    ) -> PlanMultipliersView:
        plan = await self._plan_repo.find_by_id(plan_id)
        if plan is None:
            raise EntityNotFoundError("Plan", plan_id)

        clean: list[PlanCategoryMultiplier] = []
        for category, raw in multipliers.items():
            if category not in _VALID_CATEGORIES:
                raise ValidationError(f"Unknown usage category: {category}")
            try:
                value = Decimal(str(raw))
            except (InvalidOperation, TypeError, ValueError):
                raise ValidationError(f"Invalid multiplier for {category}") from None
            if value < 0:
                raise ValidationError(f"multiplier for {category} must be >= 0")
            clean.append(PlanCategoryMultiplier(plan_id, category, value))

        before = {
            r.usage_category: str(r.multiplier)
            for r in await self._repo.list_for_plan(plan_id)
        }
        await self._repo.replace_for_plan(plan_id, clean)
        if self._billing_context is not None:
            self._billing_context.invalidate(None)
        if self._audit is not None:
            await self._audit.record(
                entity_type="plan",
                entity_id=plan_id,
                action="update",
                before={"category_multipliers": before},
                after={
                    "category_multipliers": {
                        m.usage_category: str(m.multiplier) for m in clean
                    }
                },
                actor_user_id=actor_user_id,
            )
        return PlanMultipliersView(
            plan_id=plan_id,
            default_category_multiplier=plan.default_category_multiplier,
            multipliers={m.usage_category: m.multiplier for m in clean},
        )
