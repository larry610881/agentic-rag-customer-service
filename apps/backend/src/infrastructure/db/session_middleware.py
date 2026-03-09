"""Per-request shared AsyncSession lifecycle via ContextVar + ASGI middleware.

Each request gets at most one AsyncSession (singleton per request).
On teardown the middleware rolls back any open transaction and closes the session.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ASGIApp, Receive, Scope, Send

from src.infrastructure.db.engine import async_session_factory

_logger = logging.getLogger(__name__)

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


@asynccontextmanager
async def independent_session_scope() -> AsyncIterator[None]:
    """背景任務用：重置 ContextVar 讓 get_tracked_session() 建立新 session。

    進入時將 _request_session 設為 None，使 get_tracked_session() 建立獨立
    session（不共用 request 的 connection）。離開時 close 該 session 並還原
    ContextVar，讓 middleware 仍能正常清理原本的 request session。
    """
    token = _request_session.set(None)
    try:
        yield
    finally:
        session = _request_session.get()
        _request_session.reset(token)
        if session is not None:
            try:
                if session.in_transaction():
                    await session.rollback()
            except Exception:
                _logger.warning("independent session rollback failed", exc_info=True)
            try:
                await session.close()
            except Exception:
                _logger.warning("independent session close failed", exc_info=True)


class SessionCleanupMiddleware:
    """Pure ASGI middleware — closes the shared session after each request.

    Correctly handles:
    - Normal requests (session closed after response is sent)
    - BackgroundTasks (run within ASGI scope; session closed after tasks complete)
    - SSE StreamingResponse (session stays alive during stream; closed when done)

    Uses pure ASGI instead of BaseHTTPMiddleware to avoid breaking SSE streams.

    Cleanup strategy: rollback and close are in SEPARATE try/except blocks
    so that a rollback failure never prevents close() from running.
    This prevents connection pool leaks on DB errors (FK violation, etc.).
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
                # Rollback and close in SEPARATE try/except to prevent
                # connection leaks when rollback fails.
                try:
                    if session.in_transaction():
                        await session.rollback()
                except Exception:
                    _logger.warning("session rollback failed", exc_info=True)
                try:
                    await session.close()
                except Exception:
                    _logger.warning("session close failed", exc_info=True)
                    # Last resort: invalidate the underlying connection
                    # so it doesn't stay checked out in the pool forever.
                    try:
                        await session.invalidate()
                    except Exception:
                        pass
