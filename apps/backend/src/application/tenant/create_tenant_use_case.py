from dataclasses import dataclass

from src.domain.shared.exceptions import DuplicateEntityError
from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository
from src.domain.tenant.value_objects import TenantId


@dataclass(frozen=True)
class CreateTenantCommand:
    name: str
    plan: str = "starter"


class CreateTenantUseCase:
    def __init__(self, tenant_repository: TenantRepository) -> None:
        self._tenant_repository = tenant_repository

    async def execute(self, command: CreateTenantCommand) -> Tenant:
        existing = await self._tenant_repository.find_by_name(command.name)
        if existing is not None:
            raise DuplicateEntityError("Tenant", "name", command.name)

        tenant = Tenant(
            id=TenantId(),
            name=command.name,
            plan=command.plan,
        )
        await self._tenant_repository.save(tenant)
        return tenant
