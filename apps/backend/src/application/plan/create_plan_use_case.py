"""Create Plan Use Case — S-Token-Gov.1"""

from dataclasses import dataclass
from decimal import Decimal

from src.domain.plan.entity import Plan
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


class CreatePlanUseCase:
    def __init__(self, plan_repository: PlanRepository) -> None:
        self._repo = plan_repository

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
        )
        return await self._repo.save(plan)
