"""Issue #95：Idempotency-Key 的單元測試（store 用記憶體假件 / AsyncMock Redis）。"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel
from pytest_bdd import given, parsers, scenarios, then, when
from redis.exceptions import RedisError

from src.application.shared.idempotency_guard import IdempotencyGuard
from src.domain.shared.idempotency import (
    ClaimOutcome,
    IdempotencyInProgress,
    IdempotencyKeyReused,
    IdempotencyRecord,
)
from src.infrastructure.idempotency.redis_idempotency_store import (
    RedisIdempotencyStore,
)
from src.interfaces.api.deps import CurrentTenant
from src.interfaces.api.errors import ApiError
from src.interfaces.api.idempotency import (
    idempotency_scope,
    parse_idempotency_key,
    run_idempotent,
)

scenarios("unit/interfaces/idempotency.feature")

DEFAULT_SCOPE = "t1:client:c1:agent.chat"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class MemoryStore:
    """記憶體版 IdempotencyStore：記錄每筆的 TTL 供斷言。"""

    def __init__(self) -> None:
        self.data: dict[str, tuple[IdempotencyRecord, int]] = {}

    async def claim(self, key, fingerprint, ttl_seconds):
        if key in self.data:
            return ClaimOutcome(acquired=False, existing=self.data[key][0])
        self.data[key] = (
            IdempotencyRecord(state="in_progress", fingerprint=fingerprint),
            ttl_seconds,
        )
        return ClaimOutcome(acquired=True)

    async def complete(self, key, record, ttl_seconds):
        self.data[key] = (record, ttl_seconds)

    async def release(self, key):
        self.data.pop(key, None)


class BrokenStore:
    async def claim(self, key, fingerprint, ttl_seconds):
        return ClaimOutcome(acquired=False, available=False)

    async def complete(self, key, record, ttl_seconds):
        raise AssertionError("不可用的 store 不應被 complete")

    async def release(self, key):
        raise AssertionError("不可用的 store 不應被 release")


class _Resp(BaseModel):
    answer: str
    n: int


@pytest.fixture
def ctx():
    return {"calls": 0, "results": [], "errors": [], "fail_first": False, "status": 200}


def _make_handler(ctx):
    async def handler():
        ctx["calls"] += 1
        if ctx.get("probe"):
            ctx["seen"] = ctx["store"].data.get(f"idem:{DEFAULT_SCOPE}:k1")
        if ctx["fail_first"] and ctx["calls"] == 1:
            raise RuntimeError("boom")
        return ctx["status"], {"answer": "hi", "n": ctx["calls"]}

    return handler


# ── guard ──────────────────────────────────────────────────────


@given("一個記憶體快照 store 與 guard")
def memory_guard(ctx):
    ctx["store"] = MemoryStore()
    ctx["guard"] = IdempotencyGuard(
        ctx["store"], ttl_seconds=86400, in_progress_ttl_seconds=130
    )


@given("一個不可用的 store 與 guard")
def broken_guard(ctx):
    ctx["store"] = BrokenStore()
    ctx["guard"] = IdempotencyGuard(ctx["store"])


@given(parsers.parse('store 中 "{key}" 已是處理中且指紋 "{fp}"'))
def preset_in_progress(ctx, key, fp):
    ctx["store"].data[key] = (
        IdempotencyRecord(state="in_progress", fingerprint=fp), 130
    )


@given("handler 第一次會拋例外")
def fail_first(ctx):
    ctx["fail_first"] = True


@given(parsers.parse("handler 會回狀態碼 {status:d}"))
def handler_status(ctx, status):
    ctx["status"] = status


@given("handler 會在執行中檢查 store")
def probe(ctx):
    ctx["probe"] = True


def _execute(ctx, scope, key, fp):
    try:
        result = _run(
            ctx["guard"].run(
                scope=scope, key=key, fingerprint=fp, handler=_make_handler(ctx)
            )
        )
        ctx["results"].append(result)
        ctx["errors"].append(None)
    except Exception as e:  # noqa: BLE001
        ctx["errors"].append(e)


@when(parsers.parse('以 key "{key}" 與 body 指紋 "{fp}" 執行 guard'))
def exec_default_scope(ctx, key, fp):
    _execute(ctx, DEFAULT_SCOPE, key, fp)


@when(parsers.parse('以 scope "{scope}" key "{key}" 指紋 "{fp}" 執行 guard'))
def exec_scope(ctx, scope, key, fp):
    _execute(ctx, scope, key, fp)


@then(parsers.parse("handler 執行次數為 {n:d}"))
def assert_calls(ctx, n):
    assert ctx["calls"] == n


@then("結果未標記為重播")
def not_replayed(ctx):
    assert ctx["results"][-1].replayed is False


@then("結果標記為重播")
def replayed(ctx):
    assert ctx["results"][-1].replayed is True


@then("兩次結果的 body 相同")
def same_body(ctx):
    assert ctx["results"][0].body == ctx["results"][1].body


@then(parsers.parse('store 中 "{key}" 的狀態為 "{state}" 且 TTL 為 {ttl:d}'))
def store_state(ctx, key, state, ttl):
    record, stored_ttl = ctx["store"].data[key]
    assert record.state == state
    assert stored_ttl == ttl


@then(parsers.parse('store 中不存在 "{key}"'))
def store_absent(ctx, key):
    assert key not in ctx["store"].data


@then("拋出 IdempotencyKeyReused")
def raised_reused(ctx):
    assert isinstance(ctx["errors"][-1], IdempotencyKeyReused)


@then("拋出 IdempotencyInProgress")
def raised_in_progress(ctx):
    assert isinstance(ctx["errors"][-1], IdempotencyInProgress)


@then("拋出 handler 的例外")
def raised_handler(ctx):
    assert isinstance(ctx["errors"][-1], RuntimeError)


@then(parsers.parse('handler 執行中看到的狀態為 "{state}" 且 TTL 為 {ttl:d}'))
def seen_in_progress(ctx, state, ttl):
    record, stored_ttl = ctx["seen"]
    assert record.state == state and stored_ttl == ttl


# ── 標頭解析 ───────────────────────────────────────────────────


@when(parsers.parse('以標頭值 "{value}" 解析 Idempotency-Key'))
def parse_header(ctx, value):
    if value == "(empty)":
        value = ""
    elif value == "(too-long)":
        value = "x" * 129
    try:
        ctx["parsed"] = parse_idempotency_key(value)
        ctx["parse_error"] = None
    except ApiError as e:
        ctx["parse_error"] = e


@then(parsers.parse("解析結果為 {outcome}"))
def parse_outcome(ctx, outcome):
    if outcome == "ok":
        assert ctx["parse_error"] is None and ctx["parsed"]
    else:
        assert ctx["parse_error"] is not None
        assert ctx["parse_error"].status_code == 400
        assert ctx["parse_error"].code == "invalid_idempotency_key"


# ── run_idempotent（interfaces 轉接）──────────────────────────


def _tenant():
    return CurrentTenant(tenant_id="t1", role="api_client", client_id="c1")


def _model_handler(ctx):
    async def handler():
        ctx["calls"] += 1
        return _Resp(answer="hi", n=ctx["calls"])

    return handler


@when("以無 key 呼叫 run_idempotent")
def run_no_key(ctx):
    ctx["resp"] = _run(
        run_idempotent(
            ctx["guard"],
            key=None,
            scope=idempotency_scope(_tenant(), "agent.chat"),
            fingerprint="fp",
            handler=_model_handler(ctx),
        )
    )


@then("回傳的是原始回應模型")
def is_model(ctx):
    assert isinstance(ctx["resp"], _Resp)
    assert ctx["calls"] == 1


@when(parsers.parse('以 key "{key}" 呼叫 run_idempotent 兩次'))
def run_twice(ctx, key):
    ctx["http"] = []
    for _ in range(2):
        ctx["http"].append(
            _run(
                run_idempotent(
                    ctx["guard"],
                    key=key,
                    scope=idempotency_scope(_tenant(), "agent.chat"),
                    fingerprint="fp",
                    handler=_model_handler(ctx),
                )
            )
        )


@when(parsers.parse('以 key "{key}" 呼叫 run_idempotent 一次'))
def run_once(ctx, key):
    try:
        run_idempotent_result = _run(
            run_idempotent(
                ctx["guard"],
                key=key,
                scope=idempotency_scope(_tenant(), "agent.chat"),
                fingerprint="fp",
                handler=_model_handler(ctx),
            )
        )
        ctx["http"] = [run_idempotent_result]
        ctx["api_error"] = None
    except ApiError as e:
        ctx["api_error"] = e


@then(parsers.parse('第一次回應標頭 Idempotent-Replayed 為 "{v}"'))
def first_header(ctx, v):
    assert ctx["http"][0].headers["idempotent-replayed"] == v


@then(parsers.parse('第二次回應標頭 Idempotent-Replayed 為 "{v}"'))
def second_header(ctx, v):
    assert ctx["http"][1].headers["idempotent-replayed"] == v


@then("兩次回應 body 相同")
def same_http_body(ctx):
    assert json.loads(ctx["http"][0].body) == json.loads(ctx["http"][1].body)
    assert ctx["calls"] == 1


@then(
    parsers.parse(
        '拋出 ApiError 狀態 {status:d} code "{code}" 且 Retry-After 為 "{ra}"'
    )
)
def api_error(ctx, status, code, ra):
    e = ctx["api_error"]
    assert e is not None and e.status_code == status and e.code == code
    assert e.headers["Retry-After"] == ra


# ── Redis store ────────────────────────────────────────────────


@given("一個以假 Redis 建立的 RedisIdempotencyStore")
def redis_store(ctx):
    ctx["redis"] = AsyncMock()
    ctx["rstore"] = RedisIdempotencyStore(ctx["redis"])


def _claim(ctx):
    ctx["claim"] = _run(ctx["rstore"].claim("idem:x", "fp", 130))


@when("Redis SET NX 回成功")
def redis_set_ok(ctx):
    ctx["redis"].set = AsyncMock(return_value=True)
    _claim(ctx)


@when("Redis SET NX 回失敗且 GET 回一筆 done 紀錄")
def redis_set_exists(ctx):
    ctx["redis"].set = AsyncMock(return_value=None)
    ctx["redis"].get = AsyncMock(
        return_value=json.dumps(
            {"v": 1, "state": "done", "fp": "fp", "status": 200, "body": {"a": 1}}
        ).encode()
    )
    _claim(ctx)


@when("Redis 拋出 RedisError")
def redis_error(ctx):
    ctx["redis"].set = AsyncMock(side_effect=RedisError("down"))
    _claim(ctx)


@then("claim 結果為 acquired")
def claim_acquired(ctx):
    assert ctx["claim"].acquired is True and ctx["claim"].available is True
    ctx["redis"].set.assert_awaited_once()
    kwargs = ctx["redis"].set.await_args.kwargs
    assert kwargs["nx"] is True and kwargs["ex"] == 130


@then(parsers.parse('claim 結果為 existing 且狀態 "{state}"'))
def claim_existing(ctx, state):
    assert ctx["claim"].acquired is False
    assert ctx["claim"].existing.state == state
    assert ctx["claim"].existing.body == {"a": 1}


@then("claim 結果為 unavailable")
def claim_unavailable(ctx):
    assert ctx["claim"].available is False and ctx["claim"].acquired is False
