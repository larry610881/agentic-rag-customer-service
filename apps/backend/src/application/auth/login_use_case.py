from dataclasses import dataclass

from src.domain.auth.login_attempt_tracker import LoginAttemptTracker
from src.domain.auth.password_service import PasswordService
from src.domain.auth.repository import UserRepository
from src.domain.shared.exceptions import DomainException
from src.infrastructure.logging.trace import trace_step


class AuthenticationError(DomainException):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class AccountLockedError(DomainException):
    """Issue #58：連續失敗達上限，暫時拒絕登入（含正確密碼）。"""

    def __init__(self, retry_after: int) -> None:
        super().__init__("Too many failed login attempts")
        self.retry_after = retry_after


@dataclass(frozen=True)
class LoginCommand:
    email: str
    password: str


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        password_service: PasswordService,
        jwt_service: object,
        login_attempt_tracker: LoginAttemptTracker | None = None,
    ) -> None:
        self._user_repository = user_repository
        self._password_service = password_service
        self._jwt_service = jwt_service
        # None 時（舊測試 / 未注入）行為與加固前一致
        self._tracker = login_attempt_tracker

    async def execute(self, command: LoginCommand) -> LoginResult:
        identifier = command.email.strip().lower()

        if self._tracker is not None:
            with trace_step("login_lock_check"):
                retry_after = await self._tracker.retry_after(identifier)
            if retry_after > 0:
                raise AccountLockedError(retry_after)

        with trace_step("find_by_email"):
            user = await self._user_repository.find_by_email(command.email)

        ok = False
        if user is not None:
            with trace_step("bcrypt_verify"):
                ok = self._password_service.verify_password(
                    command.password, user.hashed_password
                )

        if user is None or not ok:
            await self._on_failure(identifier)
            raise AuthenticationError()

        if self._tracker is not None:
            await self._tracker.reset(identifier)

        with trace_step("create_user_token"):
            token = self._jwt_service.create_user_token(  # type: ignore[attr-defined]
                user_id=user.id.value,
                tenant_id=user.tenant_id,
                role=user.role.value,
            )
        with trace_step("create_refresh_token"):
            refresh = self._jwt_service.create_refresh_token(  # type: ignore[attr-defined]
                user_id=user.id.value,
                tenant_id=user.tenant_id,
                role=user.role.value,
            )
        return LoginResult(access_token=token, refresh_token=refresh)

    async def _on_failure(self, identifier: str) -> None:
        if self._tracker is None:
            return
        with trace_step("login_record_failure"):
            lock_seconds = await self._tracker.record_failure(identifier)
        if lock_seconds > 0:
            raise AccountLockedError(lock_seconds)
