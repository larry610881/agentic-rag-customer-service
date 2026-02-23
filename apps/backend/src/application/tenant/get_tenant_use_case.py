from src.domain.shared.exceptions import EntityNotFoundError
from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository


class GetTenantUseCase:
    def __init__(self, tenant_repository: TenantRepository) -> None:
        self._tenant_repository = tenant_repository

    async def execute(self, tenant_id: str) -> Tenant:
        tenant = await self._tenant_repository.find_by_id(tenant_id)
        if tenant is None:
            raise EntityNotFoundError("Tenant", tenant_id)
        return tenant
