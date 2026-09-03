from dataclasses import dataclass

from src.domain.auth.entity import User
from src.domain.auth.password_service import PasswordService
from src.domain.auth.repository import UserRepository
from src.domain.auth.token_stores import TokenRevocationStore
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
        revocation_store: TokenRevocationStore | None = None,
        access_ttl_seconds: int = 900,
    ) -> None:
        self._repo = user_repository
        self._password_service = password_service
        self._revocation = revocation_store
        self._access_ttl_seconds = access_ttl_seconds

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
            token_version=existing.token_version + 1,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
        await self._repo.save(updated)
        if self._revocation is not None:
            await self._revocation.revoke_user_before(
                updated.id.value, updated.token_version, self._access_ttl_seconds
            )
