"""IdempotencyGuard — 通路無關的「執行一次或重播」（Issue #95）。

流程：claim → 執行 handler → 2xx 寫完成快照 / 否則釋放。
store 不可用一律 fail-open（與專案所有 Redis 用途一致）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import structlog

from src.domain.shared.idempotency import (
    STATE_DONE,
    STATE_IN_PROGRESS,
    IdempotencyInProgress,
    IdempotencyKeyReused,
    IdempotencyRecord,
    IdempotencyStore,
)

logger = structlog.get_logger(__name__)

Handler = Callable[[], Awaitable[tuple[int, dict[str, Any]]]]

DEFAULT_TTL_SECONDS = 86400
DEFAULT_IN_PROGRESS_TTL_SECONDS = 130  # > 請求逾時 30s、> 對話鎖 120s


@dataclass(frozen=True)
class IdempotentResult:
    status: int
    body: dict[str, Any]
    replayed: bool


class IdempotencyGuard:
    def __init__(
        self,
        store: IdempotencyStore,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        in_progress_ttl_seconds: int = DEFAULT_IN_PROGRESS_TTL_SECONDS,
    ) -> None:
        self._store = store
        self._ttl = ttl_seconds
        self._in_progress_ttl = in_progress_ttl_seconds

    async def run(
        self, *, scope: str, key: str, fingerprint: str, handler: Handler
    ) -> IdempotentResult:
        store_key = f"idem:{scope}:{key}"
        claim = await self._store.claim(store_key, fingerprint, self._in_progress_ttl)

        if not claim.available:
            logger.warning("idempotency.store_unavailable", key=store_key)
            status, body = await handler()
            return IdempotentResult(status, body, replayed=False)

        if not claim.acquired:
            existing = claim.existing
            if existing is None:
                # SET NX 失敗但 GET 已過期：極短競態，當作沒有保護執行
                status, body = await handler()
                return IdempotentResult(status, body, replayed=False)
            if existing.fingerprint != fingerprint:
                raise IdempotencyKeyReused()
            if existing.state == STATE_IN_PROGRESS:
                raise IdempotencyInProgress()
            return IdempotentResult(
                existing.status or 200, existing.body or {}, replayed=True
            )

        try:
            status, body = await handler()
        except BaseException:
            await self._store.release(store_key)
            raise

        if 200 <= status < 300:
            await self._store.complete(
                store_key,
                IdempotencyRecord(
                    state=STATE_DONE, fingerprint=fingerprint, status=status, body=body
                ),
                self._ttl,
            )
        else:
            await self._store.release(store_key)
        return IdempotentResult(status, body, replayed=False)
