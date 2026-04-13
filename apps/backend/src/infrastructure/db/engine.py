import atexit
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
    connect_args={
        # Auto-rollback sessions stuck in "idle in transaction" after 30s.
        # Prevents connection pool exhaustion from leaked transactions.
        "server_settings": {"idle_in_transaction_session_timeout": "300000"},  # 5min (OCR may take 2-3min)
    },
)

# Safety net: 確保 process exit 時（包括 SIGTERM → SystemExit）
# 同步釋放所有 pool connections，防止 hot reload 連線洩漏。
# Wrapper: interpreter shutdown 期間 module 可能已被 GC，dispose() 可能失敗。
def _dispose_engine_sync() -> None:
    try:
        engine.sync_engine.dispose()
    except Exception:
        pass


atexit.register(_dispose_engine_sync)


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
