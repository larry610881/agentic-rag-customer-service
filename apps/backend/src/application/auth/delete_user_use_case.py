from src.domain.auth.repository import UserRepository
from src.domain.shared.exceptions import EntityNotFoundError


class DeleteUserUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._repo = user_repository

    async def execute(self, user_id: str) -> None:
        existing = await self._repo.find_by_id(user_id)
        if existing is None:
            raise EntityNotFoundError("User", user_id)
        await self._repo.delete(user_id)
