"""X-Client-Version 門檻（Issue #98，準則 B4）。

純 ASGI（不可用 BaseHTTPMiddleware，見全域 CLAUDE.md 的 ContextVar 教訓）。
- 讀 `X-Client-Version` 綁進 structlog context（request log 可依版本聚合）
- `min_version` 非空且標頭可解析為 semver、低於門檻 → 426 `client_upgrade_required`
- 標頭缺席或不可解析 → 放行（瀏覽器與舊客戶端不受影響；426 是止血，不是演進策略）
"""

from __future__ import annotations

import json
import re

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

from src.interfaces.api.errors import error_body

CLIENT_VERSION_HEADER = "X-Client-Version"
_SEMVER = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?")


def parse_version(raw: str | None) -> tuple[int, int, int] | None:
    if not raw:
        return None
    m = _SEMVER.match(raw.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


class ClientVersionMiddleware:
    def __init__(self, app: ASGIApp, min_version: str = "") -> None:
        self.app = app
        self._min_raw = min_version
        self._min = parse_version(min_version)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        raw = headers.get(CLIENT_VERSION_HEADER.lower())
        if raw:
            structlog.contextvars.bind_contextvars(client_version=raw[:32])
        client = parse_version(raw)
        if self._min and client and client < self._min:
            body = json.dumps(
                error_body(
                    426,
                    f"Client version {raw} is below the minimum {self._min_raw}",
                    code="client_upgrade_required",
                    extra={"min_client_version": self._min_raw},
                ),
                ensure_ascii=False,
            ).encode()
            await send({
                "type": "http.response.start",
                "status": 426,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)
