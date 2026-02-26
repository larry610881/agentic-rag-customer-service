from src.domain.auth.entity import User
from src.domain.auth.repository import UserRepository
from src.domain.shared.exceptions import EntityNotFoundError


class GetUserUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self, user_id: str) -> User:
        user = await self._user_repository.find_by_id(user_id)
        if user is None:
            raise EntityNotFoundError("User", user_id)
        return user
