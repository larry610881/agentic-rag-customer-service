"""Change Password Use Case — S-Auth.1

租戶使用者自助變更密碼：
1. 驗證舊密碼正確 → 否則 AuthenticationError
2. 新密碼不可與舊密碼相同 → 否則 SameAsOldPasswordError
3. Hash 新密碼並 save

與 Admin 的 ResetPasswordUseCase 差別：
- 此 use case 要驗證舊密碼，使用者自用
- ResetPasswordUseCase 不驗舊密碼，admin 專用
"""
from __future__ import annotations

from dataclasses import dataclass

from src.application.auth.login_use_case import AuthenticationError
from src.domain.auth.entity import User
from src.domain.auth.password_service import PasswordService
from src.domain.auth.repository import UserRepository
from src.domain.shared.exceptions import DomainException, EntityNotFoundError


class SameAsOldPasswordError(DomainException):
    def __init__(self) -> None:
        super().__init__("New password must be different from the old password")


@dataclass(frozen=True)
class ChangePasswordCommand:
    user_id: str
    old_password: str
    new_password: str


class ChangePasswordUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        password_service: PasswordService,
    ) -> None:
        self._repo = user_repository
        self._password_service = password_service

    async def execute(self, command: ChangePasswordCommand) -> None:
        user = await self._repo.find_by_id(command.user_id)
        if user is None:
            raise EntityNotFoundError("User", command.user_id)

        if not self._password_service.verify_password(
            command.old_password, user.hashed_password
        ):
            raise AuthenticationError()

        if command.old_password == command.new_password:
            raise SameAsOldPasswordError()

        new_hash = self._password_service.hash_password(command.new_password)

        updated = User(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            hashed_password=new_hash,
            role=user.role,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        await self._repo.save(updated)
