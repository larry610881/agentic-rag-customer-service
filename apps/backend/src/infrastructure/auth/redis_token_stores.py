"""Redis 版 token 狀態儲存（Issue #67 P3）

key：
- ``rt:family:{family}`` → 最新 jti，TTL = refresh 有效期
- ``rev:user:{user_id}`` → 最低可接受 ver，TTL = access 有效期

Redis 不可用時 fail-open（與 login tracker / rate limiter 一致）：rotate 回 OK、
min_version 回 None——寧可暫時失去重用偵測，也不讓 Redis 故障變成全站登出。
"""

import structlog

from src.domain.auth.token_stores import (
    RefreshTokenStore,
    RotationResult,
    TokenRevocationStore,
)

logger = structlog.get_logger(__name__)

REVOKED = "__revoked__"
REVOKED_TTL_SECONDS = 7 * 86400

# 原子 compare-and-swap：
# family 不存在 → unknown；已撤銷或 jti 不符 → reused；相符 → 換新
_ROTATE_LUA = """
local cur = redis.call('GET', KEYS[1])
if not cur then return 'unknown' end
if cur == '__revoked__' then return 'reused' end
if cur ~= ARGV[1] then return 'reused' end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 'ok'
"""


class RedisRefreshTokenStore(RefreshTokenStore):
    def __init__(self, redis_client) -> None:  # noqa: ANN001
        self._redis = redis_client

    @staticmethod
    def _key(family: str) -> str:
        return f"rt:family:{family}"

    async def begin(self, family: str, jti: str, ttl_seconds: int) -> None:
        try:
            await self._redis.set(self._key(family), jti, ex=ttl_seconds)
        except Exception:
            logger.warning("refresh_store.redis_unavailable", op="begin")

    async def rotate(
        self, family: str, presented_jti: str, new_jti: str, ttl_seconds: int
    ) -> RotationResult:
        try:
            raw = await self._redis.eval(
                _ROTATE_LUA, 1, self._key(family), presented_jti, new_jti, ttl_seconds
            )
        except Exception:
            logger.warning("refresh_store.redis_unavailable", op="rotate")
            return RotationResult.OK
        value = raw.decode() if isinstance(raw, bytes) else str(raw)
        return RotationResult(value)

    async def revoke(self, family: str) -> None:
        try:
            # 留墓碑（TTL = refresh 最長有效期），撤銷後整個 family 任何 jti 都拒
            await self._redis.set(
                self._key(family), REVOKED, ex=REVOKED_TTL_SECONDS
            )
        except Exception:
            logger.warning("refresh_store.redis_unavailable", op="revoke")


class RedisTokenRevocationStore(TokenRevocationStore):
    def __init__(self, redis_client) -> None:  # noqa: ANN001
        self._redis = redis_client

    @staticmethod
    def _key(user_id: str) -> str:
        return f"rev:user:{user_id}"

    async def revoke_user_before(
        self, user_id: str, min_version: int, ttl_seconds: int
    ) -> None:
        try:
            await self._redis.set(self._key(user_id), str(min_version), ex=ttl_seconds)
        except Exception:
            logger.warning("revocation_store.redis_unavailable", op="revoke")

    async def min_version(self, user_id: str) -> int | None:
        try:
            raw = await self._redis.get(self._key(user_id))
        except Exception:
            logger.warning("revocation_store.redis_unavailable", op="min_version")
            return None
        if raw is None:
            return None
        value = raw.decode() if isinstance(raw, bytes) else str(raw)
        try:
            return int(value)
        except ValueError:
            return None
