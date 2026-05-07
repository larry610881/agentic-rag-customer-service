"""Layer 4 — DB engine timeout / slow-query hook unit tests.

Static config assertions + structlog capture for slow-query warning;
no real DB required (asyncpg query-cancel 行為留 integration test，本檔
只驗 helper + connect_args 設定 + threshold 邏輯)。
"""
from __future__ import annotations

import structlog

from src.infrastructure.db.engine import (
    _SLOW_QUERY_THRESHOLD_MS,
    _log_slow_query_if_needed,
    engine,
)

# ── slow query log emission ─────────────────────────────────


def test_log_slow_query_emits_warning_above_threshold():
    with structlog.testing.capture_logs() as logs:
        _log_slow_query_if_needed(_SLOW_QUERY_THRESHOLD_MS + 1, "SELECT 1")

    matches = [
        e for e in logs if e.get("event") == "db.slow_query"
    ]
    assert len(matches) == 1
    assert matches[0]["log_level"] == "warning"
    assert matches[0]["sql_prefix"] == "SELECT 1"


def test_log_slow_query_silent_below_threshold():
    with structlog.testing.capture_logs() as logs:
        _log_slow_query_if_needed(_SLOW_QUERY_THRESHOLD_MS - 1, "SELECT 1")

    assert not [
        e for e in logs if e.get("event") == "db.slow_query"
    ], "should not log when below threshold"


def test_log_slow_query_truncates_long_sql():
    long_sql = "SELECT " + ("x," * 200) + "1"
    with structlog.testing.capture_logs() as logs:
        _log_slow_query_if_needed(_SLOW_QUERY_THRESHOLD_MS + 100, long_sql)

    matches = [e for e in logs if e.get("event") == "db.slow_query"]
    assert len(matches) == 1
    assert len(matches[0]["sql_prefix"]) <= 120, (
        "sql_prefix must be truncated to ≤ 120 chars to avoid log spam"
    )


# ── connect_args / pool config asserts ──────────────────────


def test_engine_connect_args_include_command_timeout():
    """connect_args 必須含 command_timeout（asyncpg query-level 60s）。

    防止 page 50 carrefour DM 觀察到的 SQLAlchemy 30s+ TimeoutError 再現。
    """
    # asyncpg connect_args are stashed on engine.pool._creator's closure or
    # accessible via engine.url; SQLAlchemy stores them on the dialect's
    # _create_options. Easiest stable surface: engine.dialect.connect_kwargs?
    # Different SA versions differ — fall back to checking the module-level
    # dict we expose for clarity.
    from src.infrastructure.db import engine as engine_module

    assert hasattr(engine_module, "_CONNECT_ARGS"), (
        "engine module should expose _CONNECT_ARGS for static verification"
    )
    args = engine_module._CONNECT_ARGS
    assert args.get("command_timeout") == 60, (
        f"command_timeout should be 60s, got {args.get('command_timeout')}"
    )
    assert args.get("timeout") == 10, (
        f"asyncpg connect timeout should be 10s, got {args.get('timeout')}"
    )
    server_settings = args.get("server_settings", {})
    assert server_settings.get("idle_in_transaction_session_timeout") == "120000"


def test_engine_pool_pre_ping_enabled():
    """pool_pre_ping 必須開，否則 Cloud SQL 邊緣斷線 borrow 後才崩。"""
    assert engine.pool._pre_ping is True
