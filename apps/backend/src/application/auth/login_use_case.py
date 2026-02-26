from dataclasses import dataclass

from src.domain.auth.password_service import PasswordService
from src.domain.auth.repository import UserRepository
from src.domain.shared.exceptions import DomainException


class AuthenticationError(DomainException):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


@dataclass(frozen=True)
class LoginCommand:
    email: str
    password: str


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    token_type: str = "bearer"


class LoginUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        password_service: PasswordService,
        jwt_service: object,
    ) -> None:
        self._user_repository = user_repository
        self._password_service = password_service
        self._jwt_service = jwt_service

    async def execute(self, command: LoginCommand) -> LoginResult:
        user = await self._user_repository.find_by_email(command.email)
        if user is None:
            raise AuthenticationError()

        if not self._password_service.verify_password(
            command.password, user.hashed_password
        ):
            raise AuthenticationError()

        token = self._jwt_service.create_user_token(  # type: ignore[attr-defined]
            user_id=user.id.value,
            tenant_id=user.tenant_id,
            role=user.role.value,
        )
        return LoginResult(access_token=token)
