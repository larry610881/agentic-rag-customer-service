"""Delete Plan Use Case — S-Token-Gov.1

預設軟刪（is_active=False）；force=True 且無租戶綁定 → 真 delete。
"""

from src.domain.plan.repository import PlanRepository
from src.domain.shared.exceptions import DomainException, EntityNotFoundError


class DeletePlanUseCase:
    def __init__(self, plan_repository: PlanRepository) -> None:
        self._repo = plan_repository

    async def execute(self, plan_id: str, *, force: bool = False) -> None:
        plan = await self._repo.find_by_id(plan_id)
        if plan is None:
            raise EntityNotFoundError("Plan", plan_id)

        bound_count = await self._repo.count_tenants_using_plan(plan.name)

        if force:
            if bound_count > 0:
                raise DomainException(
                    f"Cannot force-delete plan '{plan.name}': "
                    f"{bound_count} tenant(s) still bound to it"
                )
            await self._repo.delete(plan_id)
        else:
            # 軟刪 — set is_active=False
            plan.is_active = False
            await self._repo.save(plan)
