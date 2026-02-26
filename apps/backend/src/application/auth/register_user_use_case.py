from dataclasses import dataclass

from src.domain.auth.entity import User
from src.domain.auth.password_service import PasswordService
from src.domain.auth.repository import UserRepository
from src.domain.auth.value_objects import Email, Role, UserId
from src.domain.shared.exceptions import DuplicateEntityError


@dataclass(frozen=True)
class RegisterUserCommand:
    email: str
    password: str
    role: str
    tenant_id: str | None = None


class RegisterUserUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        password_service: PasswordService,
    ) -> None:
        self._user_repository = user_repository
        self._password_service = password_service

    async def execute(self, command: RegisterUserCommand) -> User:
        existing = await self._user_repository.find_by_email(command.email)
        if existing is not None:
            raise DuplicateEntityError("User", "email", command.email)

        hashed = self._password_service.hash_password(command.password)

        user = User(
            id=UserId(),
            tenant_id=command.tenant_id,
            email=Email(command.email),
            hashed_password=hashed,
            role=Role(command.role),
        )
        await self._user_repository.save(user)
        return user
