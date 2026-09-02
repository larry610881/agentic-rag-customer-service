"""安全標頭中介層（security-precheck 2026-09-02：11365 / 11366 / 11359 / 11306）

Pure ASGI（禁用 BaseHTTPMiddleware，見全域 CLAUDE.md 的 ContextVar 隔離教訓）。
- 全站：HSTS、nosniff、X-Frame-Options DENY、CSP frame-ancestors 'none'、
  Referrer-Policy、Permissions-Policy
- ``/api/`` 前綴：Cache-Control: no-store（路由已自行設定者不覆蓋）
widget.js 是以 <script> 被客戶站載入，不是 iframe，frame-ancestors 'none' 不影響它。
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_BASE_HEADERS: list[tuple[bytes, bytes]] = [
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"content-security-policy", b"frame-ancestors 'none'"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]
_API_PREFIX = "/api/"


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        is_api = path.startswith(_API_PREFIX)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                for k, v in _BASE_HEADERS:
                    if k not in present:
                        headers.append((k, v))
                if is_api and b"cache-control" not in present:
                    headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
