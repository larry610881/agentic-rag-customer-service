from src.domain.auth.entity import User
from src.domain.auth.repository import UserRepository


class ListUsersUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._repo = user_repository

    async def execute(
        self,
        tenant_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[User]:
        if tenant_id:
            return await self._repo.find_all_by_tenant(
                tenant_id, limit=limit, offset=offset,
            )
        return await self._repo.find_all(
            limit=limit, offset=offset,
        )

    async def count(self, tenant_id: str | None = None) -> int:
        return await self._repo.count_all(tenant_id=tenant_id)
