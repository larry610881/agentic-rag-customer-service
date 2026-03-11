from src.domain.auth.entity import User
from src.domain.auth.repository import UserRepository


class ListUsersUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._repo = user_repository

    async def execute(self, tenant_id: str | None = None) -> list[User]:
        if tenant_id:
            return await self._repo.find_all_by_tenant(tenant_id)
        return await self._repo.find_all()
