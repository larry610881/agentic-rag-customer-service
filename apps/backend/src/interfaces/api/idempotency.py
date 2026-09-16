"""Idempotency-Key 的 HTTP 轉接（Issue #95）。

只做 I/O：讀標頭、驗格式、算 body 指紋、組 scope、把 domain 例外轉成 ApiError。
「執行一次或重播」的邏輯在 application 層 ``IdempotencyGuard``，各通路共用。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from fastapi import Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.application.shared.idempotency_guard import IdempotencyGuard, StreamClaim
from src.domain.shared.idempotency import (
    IdempotencyInProgress,
    IdempotencyKeyReused,
)
from src.interfaces.api.deps import CurrentTenant
from src.interfaces.api.errors import ApiError

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
REPLAYED_HEADER = "Idempotent-Replayed"
LAST_EVENT_ID_HEADER = "Last-Event-ID"

_KEY_RE = re.compile(r"^[\x21-\x7e]{1,128}$")  # 可見 ASCII、1–128 字元


def parse_idempotency_key(raw: str | None) -> str | None:
    """標頭缺席 → None（不啟用）；存在但格式不合 → 400。"""
    if raw is None:
        return None
    if not _KEY_RE.match(raw):
        raise ApiError(
            400,
            code="invalid_idempotency_key",
            message=(
                f"{IDEMPOTENCY_KEY_HEADER} must be 1-128 visible ASCII characters"
            ),
        )
    return raw


async def get_idempotency_key(
    idempotency_key: str | None = Header(
        default=None,
        alias=IDEMPOTENCY_KEY_HEADER,
        description=(
            "選填。1–128 可見 ASCII（建議 UUID v4）。同 key 同 body 在 24 小時內重送"
            "回同一份回應（Idempotent-Replayed: true），不會重複建立或重複計費"
        ),
    ),
) -> str | None:
    return parse_idempotency_key(idempotency_key)


def idempotency_scope(tenant: CurrentTenant, endpoint: str) -> str:
    """身份綁 scope：A 金鑰的 key 永遠打不到 B 的快照。"""
    if tenant.is_api_client:
        principal = f"client:{tenant.client_id or ''}"
    else:
        principal = f"user:{tenant.user_id or tenant.tenant_id}"
    return f"{tenant.tenant_id}:{principal}:{endpoint}"


def request_fingerprint(body: BaseModel) -> str:
    canonical = json.dumps(
        body.model_dump(mode="json"), sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_parts(*parts: str) -> str:
    """非 JSON body（multipart 上傳）的指紋：各部分以 NUL 串接後 sha256。"""
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


async def run_idempotent(
    guard: IdempotencyGuard | None,
    *,
    key: str | None,
    scope: str,
    fingerprint: str,
    handler: Callable[[], Awaitable[BaseModel]],
    status_code: int = 200,
) -> Any:
    """沒帶 key → 直接回 handler 的模型（行為與過去完全相同）。
    帶 key → 回 JSONResponse，標頭 ``Idempotent-Replayed`` 標示是否為重播。"""
    if key is None or guard is None:
        return await handler()

    async def _as_wire() -> tuple[int, dict[str, Any]]:
        model = await handler()
        return status_code, model.model_dump(mode="json")

    try:
        result = await guard.run(
            scope=scope, key=key, fingerprint=fingerprint, handler=_as_wire
        )
    except IdempotencyKeyReused as e:
        raise ApiError(422, code="idempotency_key_reused", message=e.message) from None
    except IdempotencyInProgress as e:
        raise ApiError(
            409,
            code="idempotency_in_progress",
            message=e.message,
            headers={"Retry-After": "1"},
        ) from None

    return JSONResponse(
        status_code=result.status,
        content=result.body,
        headers={REPLAYED_HEADER: "true" if result.replayed else "false"},
    )


def parse_last_event_id(raw: str | None) -> int | None:
    """SSE 重連游標：非負整數才有效，其餘視為沒帶。"""
    if raw is None:
        return None
    raw = raw.strip()
    if not raw.isdigit():
        return None
    return int(raw)


async def get_last_event_id(
    last_event_id: str | None = Header(
        default=None,
        alias=LAST_EVENT_ID_HEADER,
        description="SSE 重連游標：帶 Idempotency-Key 重送時，只補送 id 大於此值的事件",
    ),
) -> int | None:
    return parse_last_event_id(last_event_id)


FrameProducer = Callable[[], AsyncIterator[tuple[int, str]]]


async def idempotent_sse(
    guard: IdempotencyGuard | None,
    *,
    key: str | None,
    scope: str,
    fingerprint: str,
    last_event_id: int | None,
    producer: FrameProducer,
) -> tuple[AsyncIterator[str], dict[str, str]]:
    """串流版「執行一次或重播」。回傳 (frames 非同步迭代器, 要加到回應的標頭)。

    - 沒帶 key / guard 不可用：直接執行 producer
    - 首次：邊送邊錄，正常結束存快照；例外或取消 → 釋放 key
    - 重播：從快照送 seq > Last-Event-ID 的 frames，標頭 Idempotent-Replayed: true
    """
    if key is None or guard is None:
        async def _plain() -> AsyncIterator[str]:
            async for _seq, frame in producer():
                yield frame

        return _plain(), {}

    try:
        claim = await guard.begin_stream(scope=scope, key=key, fingerprint=fingerprint)
    except IdempotencyKeyReused as e:
        raise ApiError(422, code="idempotency_key_reused", message=e.message) from None
    except IdempotencyInProgress as e:
        raise ApiError(
            409,
            code="idempotency_in_progress",
            message=e.message,
            headers={"Retry-After": "1"},
        ) from None

    if claim.replayed:
        async def _replay() -> AsyncIterator[str]:
            for seq, frame in claim.frames or []:
                if last_event_id is None or seq > last_event_id:
                    yield frame

        return _replay(), {REPLAYED_HEADER: "true"}

    async def _record(c: StreamClaim) -> AsyncIterator[str]:
        frames: list[tuple[int, str]] = []
        try:
            async for seq, frame in producer():
                frames.append((seq, frame))
                yield frame
        except BaseException:
            await guard.abort_stream(c)
            raise
        await guard.finish_stream(c, frames)

    return _record(claim), {REPLAYED_HEADER: "false"}
