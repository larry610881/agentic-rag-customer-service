"""Redis-based conversation lock (SET NX EX)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog

from src.domain.shared.concurrency import ConversationLock

logger = structlog.get_logger(__name__)


class RedisConversationLock(ConversationLock):
    """Reject concurrent agent runs on the same conversation.

    Uses Redis SET NX EX for atomic lock acquisition.
    Falls back to no-lock (yield True) if Redis is unavailable.
    """

    def __init__(self, redis_client) -> None:  # noqa: ANN001
        self._redis = redis_client

    @asynccontextmanager
    async def acquire(
        self, lock_key: str, *, timeout: int = 120
    ) -> AsyncIterator[bool]:
        lock_value = uuid4().hex
        acquired = False
        try:
            result = await self._redis.set(
                lock_key, lock_value, nx=True, ex=timeout
            )
            acquired = result is not None
            yield acquired
        except Exception:
            # Redis down → degrade to no-lock
            logger.warning(
                "concurrency.redis_unavailable",
                lock_key=lock_key,
                msg="Redis 不可用，降級為無鎖模式",
            )
            yield True
            return
        finally:
            if acquired:
                try:
                    # Only delete if we still own the lock
                    current = await self._redis.get(lock_key)
                    if current == lock_value.encode():
                        await self._redis.delete(lock_key)
                except Exception:
                    logger.warning(
                        "concurrency.lock_release_failed",
                        lock_key=lock_key,
                        exc_info=True,
                    )
