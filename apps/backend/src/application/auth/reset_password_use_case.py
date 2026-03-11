from dataclasses import dataclass

from src.domain.auth.entity import User
from src.domain.auth.password_service import PasswordService
from src.domain.auth.repository import UserRepository
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class ResetPasswordCommand:
    user_id: str
    new_password: str


class ResetPasswordUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        password_service: PasswordService,
    ) -> None:
        self._repo = user_repository
        self._password_service = password_service

    async def execute(self, command: ResetPasswordCommand) -> None:
        existing = await self._repo.find_by_id(command.user_id)
        if existing is None:
            raise EntityNotFoundError("User", command.user_id)

        hashed = self._password_service.hash_password(command.new_password)

        updated = User(
            id=existing.id,
            tenant_id=existing.tenant_id,
            email=existing.email,
            hashed_password=hashed,
            role=existing.role,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
        await self._repo.save(updated)
