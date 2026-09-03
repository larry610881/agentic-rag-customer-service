"""記憶體版 token 狀態儲存（測試 / 單機開發用；Issue #67 P3）"""

import time

from src.domain.auth.token_stores import (
    RefreshTokenStore,
    RotationResult,
    TokenRevocationStore,
)

REVOKED = "__revoked__"
REVOKED_TTL_SECONDS = 7 * 86400


class InMemoryRefreshTokenStore(RefreshTokenStore):
    def __init__(self) -> None:
        self._families: dict[str, tuple[str, float]] = {}

    def _current(self, family: str) -> str | None:
        entry = self._families.get(family)
        if entry is None:
            return None
        jti, expires = entry
        if expires <= time.monotonic():
            self._families.pop(family, None)
            return None
        return jti

    async def begin(self, family: str, jti: str, ttl_seconds: int) -> None:
        self._families[family] = (jti, time.monotonic() + ttl_seconds)

    async def rotate(
        self, family: str, presented_jti: str, new_jti: str, ttl_seconds: int
    ) -> RotationResult:
        current = self._current(family)
        if current is None:
            return RotationResult.UNKNOWN
        if current == REVOKED or current != presented_jti:
            return RotationResult.REUSED
        self._families[family] = (new_jti, time.monotonic() + ttl_seconds)
        return RotationResult.OK

    async def revoke(self, family: str) -> None:
        # 留墓碑：撤銷後整個 family 任何 jti 都視為重用
        self._families[family] = (REVOKED, time.monotonic() + REVOKED_TTL_SECONDS)


class InMemoryTokenRevocationStore(TokenRevocationStore):
    def __init__(self) -> None:
        self._min: dict[str, tuple[int, float]] = {}

    async def revoke_user_before(
        self, user_id: str, min_version: int, ttl_seconds: int
    ) -> None:
        self._min[user_id] = (min_version, time.monotonic() + ttl_seconds)

    async def min_version(self, user_id: str) -> int | None:
        entry = self._min.get(user_id)
        if entry is None:
            return None
        version, expires = entry
        if expires <= time.monotonic():
            self._min.pop(user_id, None)
            return None
        return version
