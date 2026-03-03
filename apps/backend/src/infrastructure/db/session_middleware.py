"""Per-request shared AsyncSession lifecycle via ContextVar + ASGI middleware.

Each request gets at most one AsyncSession (singleton per request).
On teardown the middleware rolls back any open transaction and closes the session.
"""

from __future__ import annotations

from contextvars import ContextVar

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Receive, Scope, Send

from src.infrastructure.db.engine import async_session_factory

_request_session: ContextVar[AsyncSession | None] = ContextVar(
    "_request_session", default=None
)


def get_tracked_session() -> AsyncSession:
    """Return the per-request shared session, creating on first call."""
    session = _request_session.get()
    if session is not None:
        return session
    session = async_session_factory()
    _request_session.set(session)
    return session


class SessionCleanupMiddleware:
    """Pure ASGI middleware — closes the shared session after each request.

    Correctly handles:
    - Normal requests (session closed after response is sent)
    - BackgroundTasks (run within ASGI scope; session closed after tasks complete)
    - SSE StreamingResponse (session stays alive during stream; closed when done)

    Uses pure ASGI instead of BaseHTTPMiddleware to avoid breaking SSE streams.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        token = _request_session.set(None)
        try:
            await self.app(scope, receive, send)
        finally:
            session = _request_session.get()
            _request_session.reset(token)
            if session is not None:
                try:
                    if session.in_transaction():
                        await session.rollback()
                    await session.close()
                except Exception:
                    pass
