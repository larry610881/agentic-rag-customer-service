import time
from dataclasses import dataclass

import structlog

from src.domain.auth.password_service import PasswordService
from src.domain.auth.repository import UserRepository
from src.domain.shared.exceptions import DomainException

_trace = structlog.get_logger("trace")


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
        t0 = time.perf_counter()
        user = await self._user_repository.find_by_email(command.email)
        _trace.info("trace.step", step="find_by_email", elapsed_ms=round((time.perf_counter() - t0) * 1000, 1))
        if user is None:
            raise AuthenticationError()

        t0 = time.perf_counter()
        ok = self._password_service.verify_password(
            command.password, user.hashed_password
        )
        _trace.info("trace.step", step="bcrypt_verify", elapsed_ms=round((time.perf_counter() - t0) * 1000, 1))
        if not ok:
            raise AuthenticationError()

        t0 = time.perf_counter()
        token = self._jwt_service.create_user_token(  # type: ignore[attr-defined]
            user_id=user.id.value,
            tenant_id=user.tenant_id,
            role=user.role.value,
        )
        _trace.info("trace.step", step="create_user_token", elapsed_ms=round((time.perf_counter() - t0) * 1000, 1))
        return LoginResult(access_token=token)
