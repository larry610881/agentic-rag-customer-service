"""Idempotency-Key 的 HTTP 轉接（Issue #95）。

只做 I/O：讀標頭、驗格式、算 body 指紋、組 scope、把 domain 例外轉成 ApiError。
「執行一次或重播」的邏輯在 application 層 ``IdempotencyGuard``，各通路共用。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.application.shared.idempotency_guard import IdempotencyGuard
from src.domain.shared.idempotency import (
    IdempotencyInProgress,
    IdempotencyKeyReused,
)
from src.interfaces.api.deps import CurrentTenant
from src.interfaces.api.errors import ApiError

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
REPLAYED_HEADER = "Idempotent-Replayed"

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


async def get_idempotency_key(request: Request) -> str | None:
    return parse_idempotency_key(request.headers.get(IDEMPOTENCY_KEY_HEADER))


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


async def run_idempotent(
    guard: IdempotencyGuard | None,
    *,
    key: str | None,
    scope: str,
    fingerprint: str,
    handler: Callable[[], Awaitable[BaseModel]],
) -> Any:
    """沒帶 key → 直接回 handler 的模型（行為與過去完全相同）。
    帶 key → 回 JSONResponse，標頭 ``Idempotent-Replayed`` 標示是否為重播。"""
    if key is None or guard is None:
        return await handler()

    async def _as_wire() -> tuple[int, dict[str, Any]]:
        model = await handler()
        return 200, model.model_dump(mode="json")

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
