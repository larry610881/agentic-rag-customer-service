"""List Plans Use Case — S-Token-Gov.1"""

from src.domain.plan.entity import Plan
from src.domain.plan.repository import PlanRepository


class ListPlansUseCase:
    def __init__(self, plan_repository: PlanRepository) -> None:
        self._repo = plan_repository

    async def execute(self, *, include_inactive: bool = True) -> list[Plan]:
        return await self._repo.find_all(include_inactive=include_inactive)
