from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository


class ListTenantsUseCase:
    def __init__(self, tenant_repository: TenantRepository) -> None:
        self._tenant_repository = tenant_repository

    async def execute(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Tenant]:
        return await self._tenant_repository.find_all(
            limit=limit, offset=offset,
        )

    async def count(self) -> int:
        return await self._tenant_repository.count_all()
