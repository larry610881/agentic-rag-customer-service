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


DEFAULT_STREAM_MAX_BYTES = 512 * 1024


@dataclass
class StreamClaim:
    """串流的冪等認領結果（Issue #99）。

    - store_key None：沒有保護（沒帶 key 或 store 不可用），照常執行
    - replayed True：從快照重播，frames 為 [(seq, frame), ...]
    """

    store_key: str | None
    fingerprint: str
    replayed: bool = False
    frames: list[tuple[int, str]] | None = None


class IdempotencyGuard:
    def __init__(
        self,
        store: IdempotencyStore,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        in_progress_ttl_seconds: int = DEFAULT_IN_PROGRESS_TTL_SECONDS,
        stream_max_bytes: int = DEFAULT_STREAM_MAX_BYTES,
    ) -> None:
        self._store = store
        self._ttl = ttl_seconds
        self._in_progress_ttl = in_progress_ttl_seconds
        self._stream_max_bytes = stream_max_bytes

    # ── 串流：認領 → 產生 frames 邊送邊錄 → 完成存快照 / 失敗釋放 ──

    async def begin_stream(
        self, *, scope: str, key: str | None, fingerprint: str
    ) -> StreamClaim:
        if key is None:
            return StreamClaim(store_key=None, fingerprint=fingerprint)
        store_key = f"idem:{scope}:{key}"
        claim = await self._store.claim(store_key, fingerprint, self._in_progress_ttl)
        if not claim.available:
            logger.warning("idempotency.store_unavailable", key=store_key)
            return StreamClaim(store_key=None, fingerprint=fingerprint)
        if claim.acquired:
            return StreamClaim(store_key=store_key, fingerprint=fingerprint)
        existing = claim.existing
        if existing is None:
            return StreamClaim(store_key=None, fingerprint=fingerprint)
        if existing.fingerprint != fingerprint:
            raise IdempotencyKeyReused()
        if existing.state == STATE_IN_PROGRESS:
            raise IdempotencyInProgress()
        raw = (existing.body or {}).get("frames") or []
        frames = [(int(seq), str(frame)) for seq, frame in raw]
        return StreamClaim(
            store_key=store_key, fingerprint=fingerprint, replayed=True, frames=frames
        )

    async def finish_stream(
        self, claim: StreamClaim, frames: list[tuple[int, str]]
    ) -> None:
        """整段事件存成快照；超過大小上限就不存（釋放 key，重送會真的重跑）。"""
        if claim.store_key is None or claim.replayed:
            return
        size = sum(len(f.encode("utf-8")) for _, f in frames)
        if size > self._stream_max_bytes:
            logger.info(
                "idempotency.stream_snapshot_skipped", key=claim.store_key, bytes=size
            )
            await self._store.release(claim.store_key)
            return
        await self._store.complete(
            claim.store_key,
            IdempotencyRecord(
                state=STATE_DONE,
                fingerprint=claim.fingerprint,
                status=200,
                body={"stream": True, "frames": [[s, f] for s, f in frames]},
            ),
            self._ttl,
        )

    async def abort_stream(self, claim: StreamClaim) -> None:
        if claim.store_key is not None and not claim.replayed:
            await self._store.release(claim.store_key)

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
