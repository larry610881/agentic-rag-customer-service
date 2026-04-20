"""Get Plan Use Case — S-Token-Gov.1"""

from src.domain.plan.entity import Plan
from src.domain.plan.repository import PlanRepository
from src.domain.shared.exceptions import EntityNotFoundError


class GetPlanUseCase:
    def __init__(self, plan_repository: PlanRepository) -> None:
        self._repo = plan_repository

    async def execute(self, plan_id: str) -> Plan:
        plan = await self._repo.find_by_id(plan_id)
        if plan is None:
            raise EntityNotFoundError("Plan", plan_id)
        return plan
