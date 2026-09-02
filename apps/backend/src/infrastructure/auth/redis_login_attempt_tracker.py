"""Redis 登入失敗追蹤（Issue #58）

key：
- ``login:fail:{identifier}``  失敗計數，INCR + 視窗 TTL
- ``login:lock:{identifier}``  鎖定旗標，TTL = 鎖定秒數（剩餘秒數即 retry_after）

Redis 不可用時 fail-open（不鎖、不計數），與 rate limiter / conversation lock 一致：
寧可暫時失去防護，也不讓 Redis 故障變成全站無法登入。
"""

import structlog

from src.domain.auth.login_attempt_tracker import (
    LoginAttemptTracker,
    LoginLockoutPolicy,
)

logger = structlog.get_logger(__name__)


class RedisLoginAttemptTracker(LoginAttemptTracker):
    def __init__(self, redis_client, policy: LoginLockoutPolicy) -> None:  # noqa: ANN001
        self._redis = redis_client
        self._policy = policy

    @staticmethod
    def _fail_key(identifier: str) -> str:
        return f"login:fail:{identifier}"

    @staticmethod
    def _lock_key(identifier: str) -> str:
        return f"login:lock:{identifier}"

    async def retry_after(self, identifier: str) -> int:
        try:
            ttl = await self._redis.ttl(self._lock_key(identifier))
        except Exception:
            logger.warning("login_lockout.redis_unavailable", op="retry_after")
            return 0
        return int(ttl) if ttl and ttl > 0 else 0

    async def record_failure(self, identifier: str) -> int:
        fail_key = self._fail_key(identifier)
        try:
            count = await self._redis.incr(fail_key)
            if count == 1:
                await self._redis.expire(
                    fail_key, self._policy.failure_window_seconds
                )
            if count >= self._policy.max_failures:
                await self._redis.set(
                    self._lock_key(identifier), "1",
                    ex=self._policy.lockout_seconds,
                )
                await self._redis.delete(fail_key)
                logger.warning(
                    "login_lockout.locked",
                    identifier=identifier,
                    failures=count,
                    lockout_seconds=self._policy.lockout_seconds,
                )
                return self._policy.lockout_seconds
        except Exception:
            logger.warning("login_lockout.redis_unavailable", op="record_failure")
            return 0
        return 0

    async def reset(self, identifier: str) -> None:
        try:
            await self._redis.delete(
                self._fail_key(identifier), self._lock_key(identifier)
            )
        except Exception:
            logger.warning("login_lockout.redis_unavailable", op="reset")
