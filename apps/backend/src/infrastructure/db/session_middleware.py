"""Per-request AsyncSession lifecycle management via ContextVar + ASGI middleware.

Solves the "idle in transaction" connection leak: every AsyncSession created
during a request is tracked and closed when the request finishes.
"""

from __future__ import annotations

from contextvars import ContextVar

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Receive, Scope, Send

from src.infrastructure.db.engine import async_session_factory

_request_sessions: ContextVar[list[AsyncSession]] = ContextVar("_request_sessions")


def get_tracked_session() -> AsyncSession:
    """Create an AsyncSession and register it for per-request cleanup."""
    session = async_session_factory()
    try:
        sessions = _request_sessions.get()
    except LookupError:
        sessions = []
        _request_sessions.set(sessions)
    sessions.append(session)
    return session


class SessionCleanupMiddleware:
    """Pure ASGI middleware — closes all tracked sessions after each request.

    Correctly handles:
    - Normal requests (sessions closed after response is sent)
    - BackgroundTasks (run within ASGI scope; sessions closed after tasks complete)
    - SSE StreamingResponse (sessions stay alive during stream; closed when done)

    Uses pure ASGI instead of BaseHTTPMiddleware to avoid breaking SSE streams.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        sessions: list[AsyncSession] = []
        token = _request_sessions.set(sessions)
        try:
            await self.app(scope, receive, send)
        finally:
            _request_sessions.reset(token)
            for session in sessions:
                try:
                    await session.close()
                except Exception:
                    pass
