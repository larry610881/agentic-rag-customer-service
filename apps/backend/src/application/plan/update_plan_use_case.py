"""Update Plan Use Case — S-Token-Gov.1

不允許改 name（要改就刪除重建）；其他欄位可改。
"""

from dataclasses import dataclass
from decimal import Decimal

from src.domain.plan.entity import Plan
from src.domain.plan.repository import PlanRepository
from src.domain.shared.exceptions import DomainException, EntityNotFoundError


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


class UpdatePlanUseCase:
    def __init__(self, plan_repository: PlanRepository) -> None:
        self._repo = plan_repository

    async def execute(self, command: UpdatePlanCommand) -> Plan:
        plan = await self._repo.find_by_id(command.plan_id)
        if plan is None:
            raise EntityNotFoundError("Plan", command.plan_id)

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

        return await self._repo.save(plan)
