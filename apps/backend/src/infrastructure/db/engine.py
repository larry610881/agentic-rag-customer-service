import time

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.infrastructure.logging.trace import record_sql

_is_cloud = bool(settings.database_url_override)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=50 if _is_cloud else 20,
    max_overflow=50 if _is_cloud else 30,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=10,  # Fail fast instead of waiting 30s for a connection
)


# --- SQL query timing (buffered, only flushed for slow requests) ---
@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _before_exec(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start", []).append(time.perf_counter())


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _after_exec(conn, cursor, statement, parameters, context, executemany):
    stack = conn.info.get("query_start")
    if stack:
        elapsed_ms = round((time.perf_counter() - stack.pop()) * 1000, 1)
        record_sql(elapsed_ms, statement[:120])


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
