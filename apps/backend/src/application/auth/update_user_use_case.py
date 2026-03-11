from dataclasses import dataclass

from src.domain.auth.entity import User
from src.domain.auth.repository import UserRepository
from src.domain.auth.value_objects import Role
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class UpdateUserCommand:
    user_id: str
    role: str | None = None
    tenant_id: str | None = None


class UpdateUserUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._repo = user_repository

    async def execute(self, command: UpdateUserCommand) -> User:
        existing = await self._repo.find_by_id(command.user_id)
        if existing is None:
            raise EntityNotFoundError("User", command.user_id)

        new_role = Role(command.role) if command.role else existing.role
        new_tenant_id = (
            command.tenant_id if command.tenant_id is not None else existing.tenant_id
        )

        updated = User(
            id=existing.id,
            tenant_id=new_tenant_id,
            email=existing.email,
            hashed_password=existing.hashed_password,
            role=new_role,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
        await self._repo.save(updated)
        return updated
