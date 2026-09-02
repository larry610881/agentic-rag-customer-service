"""請求 SQL trace 持久化閘控 BDD Step Definitions（Issue #59）"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.logging import trace as trace_mod

scenarios("unit/logging/request_trace_persistence.feature")


@pytest.fixture
def context():
    return {}


@given(parsers.parse("trace 門檻為 {ms:d} 毫秒"))
def set_threshold(monkeypatch, ms):
    monkeypatch.setattr(trace_mod, "_get_threshold_ms", lambda: ms)


@given(parsers.parse("請求期間記錄了 {n:d} 個 trace 步驟"))
def record_steps(n):
    trace_mod.init_trace()
    for i in range(n):
        trace_mod.record_sql(1.5, f"SELECT {i}")


@when(parsers.parse("以請求耗時 {ms:d} 毫秒 flush trace"))
def do_flush(context, ms):
    context["result"] = trace_mod.flush_trace(float(ms))


@then("flush 結果應為 None")
def flush_none(context):
    assert context["result"] is None


@then(parsers.parse("flush 結果應含 {n:d} 個步驟"))
def flush_has(context, n):
    assert context["result"] is not None and len(context["result"]) == n
