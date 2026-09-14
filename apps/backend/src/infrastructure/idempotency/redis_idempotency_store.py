"""Redis 版 IdempotencyStore（Issue #95）。

``SET idem:{scope}:{key} <json> NX EX ttl`` 搶佔；成功後同 key 覆寫為完成快照並換 TTL。
Redis 不可用 → ``ClaimOutcome(available=False)``，由 guard fail-open。
寫法與 ``redis_webhook_event_deduplicator.py`` 同型。
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from redis.exceptions import RedisError

from src.domain.shared.idempotency import (
    STATE_IN_PROGRESS,
    ClaimOutcome,
    IdempotencyRecord,
)

logger = structlog.get_logger(__name__)

_SCHEMA_VERSION = 1


def _encode(record: IdempotencyRecord) -> str:
    return json.dumps(
        {
            "v": _SCHEMA_VERSION,
            "state": record.state,
            "fp": record.fingerprint,
            "status": record.status,
            "body": record.body,
        },
        ensure_ascii=False,
    )


def _decode(raw: Any) -> IdempotencyRecord | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return IdempotencyRecord(
        state=str(data.get("state", "")),
        fingerprint=str(data.get("fp", "")),
        status=data.get("status"),
        body=data.get("body"),
    )


class RedisIdempotencyStore:
    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def claim(
        self, key: str, fingerprint: str, ttl_seconds: int
    ) -> ClaimOutcome:
        marker = IdempotencyRecord(state=STATE_IN_PROGRESS, fingerprint=fingerprint)
        try:
            result = await self._redis.set(
                key, _encode(marker), nx=True, ex=ttl_seconds
            )
            if result:
                return ClaimOutcome(acquired=True)
            return ClaimOutcome(
                acquired=False, existing=_decode(await self._redis.get(key))
            )
        except RedisError:
            logger.warning("idempotency.redis_unavailable", key=key)
            return ClaimOutcome(acquired=False, available=False)

    async def complete(
        self, key: str, record: IdempotencyRecord, ttl_seconds: int
    ) -> None:
        try:
            await self._redis.set(key, _encode(record), ex=ttl_seconds)
        except RedisError:
            logger.warning("idempotency.redis_complete_failed", key=key)

    async def release(self, key: str) -> None:
        try:
            await self._redis.delete(key)
        except RedisError:
            logger.warning("idempotency.redis_release_failed", key=key)
