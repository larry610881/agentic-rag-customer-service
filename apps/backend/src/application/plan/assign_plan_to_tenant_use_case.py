"""Assign Plan to Tenant Use Case — S-Token-Gov.1

驗證 plan exists & is_active，然後改 tenant.plan。
"""

from src.domain.plan.repository import PlanRepository
from src.domain.shared.exceptions import DomainException, EntityNotFoundError
from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository


class AssignPlanToTenantUseCase:
    def __init__(
        self,
        plan_repository: PlanRepository,
        tenant_repository: TenantRepository,
    ) -> None:
        self._plan_repo = plan_repository
        self._tenant_repo = tenant_repository

    async def execute(self, *, plan_name: str, tenant_id: str) -> Tenant:
        plan = await self._plan_repo.find_by_name(plan_name)
        if plan is None:
            raise EntityNotFoundError("Plan", plan_name)
        if not plan.is_active:
            raise DomainException(
                f"Plan '{plan_name}' is inactive and cannot be assigned"
            )

        tenant = await self._tenant_repo.find_by_id(tenant_id)
        if tenant is None:
            raise EntityNotFoundError("Tenant", tenant_id)

        tenant.plan = plan_name
        await self._tenant_repo.save(tenant)
        return tenant
