"""Refresh token 換票（Issue #67 P3）

每次旋轉、重用即撤銷整個 family、ver 不符即拒。
"""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from src.domain.auth.repository import UserRepository
from src.domain.auth.token_stores import RefreshTokenStore, RotationResult
from src.domain.shared.exceptions import DomainException


class InvalidRefreshTokenError(DomainException):
    def __init__(self, reason: str = "Invalid or expired refresh token") -> None:
        super().__init__(reason)


@dataclass(frozen=True)
class RefreshResult:
    access_token: str
    refresh_token: str


class RefreshTokenUseCase:
    def __init__(
        self,
        jwt_service: Any,
        user_repository: UserRepository,
        refresh_store: RefreshTokenStore | None = None,
    ) -> None:
        self._jwt = jwt_service
        self._users = user_repository
        self._store = refresh_store

    async def execute(self, refresh_token: str) -> RefreshResult:
        try:
            payload = self._jwt.decode_token(refresh_token)
        except ValueError:
            raise InvalidRefreshTokenError() from None

        token_type = payload.get("type")
        if token_type not in ("refresh", "tenant_refresh"):
            raise InvalidRefreshTokenError("Invalid token type for refresh")

        family = await self._rotate_family(payload)
        new_jti = self._new_jti_for(family)
        sub = payload.get("sub", "")

        if token_type == "refresh":
            user = await self._users.find_by_id(sub)
            if user is None:
                raise InvalidRefreshTokenError()
            presented_ver = payload.get("ver")
            if presented_ver is not None and presented_ver != user.token_version:
                # 改密碼 / 重設密碼後的舊 refresh
                raise InvalidRefreshTokenError()
            access = self._jwt.create_user_token(
                user_id=user.id.value,
                tenant_id=user.tenant_id,
                role=user.role.value,
                version=user.token_version,
            )
            refresh = self._jwt.create_refresh_token(
                user_id=user.id.value,
                tenant_id=user.tenant_id,
                role=user.role.value,
                version=user.token_version,
                family=family,
                jti=new_jti,
            )
        else:
            access = self._jwt.create_tenant_token(sub)
            refresh = self._jwt.create_tenant_refresh_token(
                sub, family=family, jti=new_jti
            )
        return RefreshResult(access_token=access, refresh_token=refresh)

    # family 旋轉：把新 jti 暫存到 self._pending，避免 rotate 與簽票用到不同 jti
    async def _rotate_family(self, payload: dict) -> str:
        family = payload.get("family")
        old_jti = payload.get("jti")
        new_jti = str(uuid4())
        ttl = int(self._jwt.refresh_token_ttl_seconds)
        if self._store is None:
            self._pending = (family or str(uuid4()), new_jti)
            return self._pending[0]
        if family and old_jti:
            result = await self._store.rotate(family, old_jti, new_jti, ttl)
            if result is RotationResult.REUSED:
                await self._store.revoke(family)
                raise InvalidRefreshTokenError("Refresh token reuse detected")
            if result is RotationResult.UNKNOWN:
                # 登入早於本機制或 Redis 遺失：fail-open，從這張票重新開 family
                await self._store.begin(family, new_jti, ttl)
        else:
            family = str(uuid4())
            await self._store.begin(family, new_jti, ttl)
        self._pending = (family, new_jti)
        return family

    def _new_jti_for(self, family: str) -> str:
        pending = getattr(self, "_pending", None)
        if pending and pending[0] == family:
            return pending[1]
        return str(uuid4())
