import atexit
import time

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.infrastructure.logging.trace import record_sql

_is_cloud = bool(settings.database_url_override)

# === Layer 4: explicit asyncpg timeouts + slow-query hook ===========
#
# 5/6 carrefour DM page 50 觀察到 SQLAlchemy TimeoutError 30s+，根因是
# 沒設 asyncpg-level command_timeout，Cloud SQL 端慢查詢拖垮整個 worker。
# 補：
# - timeout=10 — asyncpg connect timeout（建連線本身上限）
# - command_timeout=60 — 單 SQL 執行 60s 上限（防 page 50 卡死）
# - idle_in_transaction_session_timeout=120000 — 維持原值，OCR /
#   Contextual Enrichment 流程已用 close-session/refresh pattern 主動處理
#   長操作，120s 給合理 batch insert 餘裕。不縮 30s。
# 另在 SQL event hook 加 slow_query (>5s) warning，方便日後盯類似 page 50。

_CONNECT_ARGS: dict = {
    # PostgreSQL 端：transaction idle 超 120s 自動 rollback + 斷線。
    "server_settings": {"idle_in_transaction_session_timeout": "120000"},
    # asyncpg connect 階段上限 — 防 DNS / 網路問題卡住 worker 啟動。
    "timeout": 10,
    # asyncpg 單 SQL 執行上限。Web API 用 60s 已夠（user 不會等更久），但
    # worker 內 split_pdf / batch process_document 並行多 task 時，event
    # loop 被其他卡住的 task（如 Milvus reconnect）拖慢，個別 INSERT 排隊
    # 可能超 60s 被 asyncpg 強制 cancel → TimeoutError → worker_resilience
    # 視為 transient 觸發 retry → split_pdf 不 idempotent 重跑製造混亂
    # （實證：5/7 user 重 upload，64 頁只切 36 個 child docs）。
    # 放寬 300s（5 min）給 worker batch 操作充分餘裕，仍是「太久必砍」防護。
    "command_timeout": 300,
}

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=50 if _is_cloud else 20,
    max_overflow=50 if _is_cloud else 30,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=10,  # Fail fast instead of waiting 30s for a connection
    connect_args=_CONNECT_ARGS,
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

_db_logger = structlog.get_logger("db")
_SLOW_QUERY_THRESHOLD_MS: float = 5000.0  # 5s — Layer 4 observability


def _log_slow_query_if_needed(elapsed_ms: float, statement: str) -> None:
    """Emit a warning for any single SQL ≥ threshold.

    Single-call surface kept testable in isolation（避免在 unit test 裡
    要建一個真 engine 才能驗 slow-log 行為）。
    """
    if elapsed_ms >= _SLOW_QUERY_THRESHOLD_MS:
        _db_logger.warning(
            "db.slow_query",
            elapsed_ms=round(elapsed_ms, 1),
            sql_prefix=statement[:120],
        )


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _before_exec(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start", []).append(time.perf_counter())


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _after_exec(conn, cursor, statement, parameters, context, executemany):
    stack = conn.info.get("query_start")
    if stack:
        elapsed_ms = round((time.perf_counter() - stack.pop()) * 1000, 1)
        record_sql(elapsed_ms, statement[:120])
        _log_slow_query_if_needed(elapsed_ms, statement)


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
