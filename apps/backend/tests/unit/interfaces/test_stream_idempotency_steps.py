"""Issue #99 一-1：串流冪等（快照重播 + Last-Event-ID）。"""

import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.shared.idempotency_guard import IdempotencyGuard
from src.domain.shared.idempotency import ClaimOutcome, IdempotencyRecord
from src.interfaces.api.errors import ApiError
from src.interfaces.api.idempotency import idempotent_sse, parse_last_event_id

scenarios("unit/interfaces/stream_idempotency.feature")

SCOPE = "t1:client:c1:agent.chat.stream"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class MemoryStore:
    def __init__(self) -> None:
        self.data: dict[str, IdempotencyRecord] = {}

    async def claim(self, key, fingerprint, ttl_seconds):
        if key in self.data:
            return ClaimOutcome(acquired=False, existing=self.data[key])
        self.data[key] = IdempotencyRecord(
            state="in_progress", fingerprint=fingerprint
        )
        return ClaimOutcome(acquired=True)

    async def complete(self, key, record, ttl_seconds):
        self.data[key] = record

    async def release(self, key):
        self.data.pop(key, None)


@pytest.fixture
def ctx():
    return {"calls": 0, "fail_after": None, "runs": []}


def _make_producer(ctx):
    async def producer():
        ctx["calls"] += 1
        for seq in (1, 2, 3):
            if ctx["fail_after"] is not None and seq > ctx["fail_after"]:
                raise RuntimeError("boom")
            yield seq, f'id: {seq}\ndata: {{"type": "token", "seq": {seq}}}\n\n'

    return producer


@given("一個記憶體快照 store 與串流 guard")
def guard(ctx):
    ctx["store"] = MemoryStore()
    ctx["guard"] = IdempotencyGuard(ctx["store"])


@given(parsers.parse("一個記憶體快照 store 與上限 {limit:d} bytes 的串流 guard"))
def small_guard(ctx, limit):
    ctx["store"] = MemoryStore()
    ctx["guard"] = IdempotencyGuard(ctx["store"], stream_max_bytes=limit)


@given(parsers.parse('快照 store 中 "{key}" 已是處理中且指紋 "{fp}"'))
def preset(ctx, key, fp):
    ctx["store"].data[key] = IdempotencyRecord(state="in_progress", fingerprint=fp)


@given("producer 會在第二個事件後拋例外")
def fail_after_two(ctx):
    ctx["fail_after"] = 2


async def _stream(ctx, key, fingerprint="fp", last_event_id=None):
    frames, headers = await idempotent_sse(
        ctx["guard"],
        key=key,
        scope=SCOPE,
        fingerprint=fingerprint,
        last_event_id=last_event_id,
        producer=_make_producer(ctx),
    )
    out = []
    async for frame in frames:
        out.append(frame)
    return out, headers


def _do(ctx, key, fingerprint="fp", last_event_id=None):
    try:
        out, headers = _run(_stream(ctx, key, fingerprint, last_event_id))
        ctx["runs"].append((out, headers))
        ctx["error"] = None
    except Exception as e:  # noqa: BLE001
        ctx["error"] = e


@when(parsers.parse('以 key "{key}" 執行串流三個事件'))
def stream_with_key(ctx, key):
    _do(ctx, key)


@when(parsers.parse('以 key "{key}" 再執行串流'))
def stream_again(ctx, key):
    _do(ctx, key)


@when(parsers.parse('以 key "{key}" 與 Last-Event-ID {last:d} 再執行串流'))
def stream_resume(ctx, key, last):
    _do(ctx, key, last_event_id=last)


@when(parsers.parse('以 key "{key}" 但指紋 "{fp}" 開始串流'))
def stream_other_fp(ctx, key, fp):
    _do(ctx, key, fingerprint=fp)


@when(parsers.parse('以 key "{key}" 直接開始串流'))
def stream_start(ctx, key):
    _do(ctx, key)


@when("不帶 key 執行串流三個事件")
def stream_no_key(ctx):
    _do(ctx, None)


@then(parsers.parse("收到 {n:d} 個 frame 且 producer 執行次數為 {calls:d}"))
def got_frames(ctx, n, calls):
    assert len(ctx["runs"][-1][0]) == n
    assert ctx["calls"] == calls


@then(parsers.parse('快照 "{key}" 含 {n:d} 個事件'))
def snapshot_has(ctx, key, n):
    rec = ctx["store"].data[key]
    assert rec.state == "done"
    assert len(rec.body["frames"]) == n


@then(parsers.parse("第二次收到與第一次相同的 {n:d} 個 frame"))
def same_frames(ctx, n):
    assert ctx["runs"][0][0] == ctx["runs"][1][0]
    assert len(ctx["runs"][1][0]) == n


@then(parsers.parse("producer 執行次數為 {calls:d}"))
def producer_calls(ctx, calls):
    assert ctx["calls"] == calls


@then("第二次 claim 標記為重播")
def second_replayed(ctx):
    assert ctx["runs"][1][1]["Idempotent-Replayed"] == "true"
    assert ctx["runs"][0][1]["Idempotent-Replayed"] == "false"


@then(parsers.parse("第二次只收到 seq {seq:d} 的 frame"))
def only_tail(ctx, seq):
    frames = ctx["runs"][1][0]
    assert len(frames) == 1 and frames[0].startswith(f"id: {seq}\n")


@then(parsers.parse('回 ApiError {status:d} "{code}"'))
def api_error(ctx, status, code):
    e = ctx["error"]
    assert isinstance(e, ApiError) and e.status_code == status and e.code == code, e


@then("拋出 producer 的例外")
def producer_error(ctx):
    assert isinstance(ctx["error"], RuntimeError)


@then(parsers.parse('快照 store 中不存在 "{key}"'))
def absent(ctx, key):
    assert key not in ctx["store"].data


@then("快照 store 是空的")
def store_empty(ctx):
    assert ctx["store"].data == {}


@when(parsers.parse('解析 Last-Event-ID "{raw}"'))
def parse_header(ctx, raw):
    ctx["parsed"] = parse_last_event_id(raw)


@then(parsers.parse("解析結果為 {value}"))
def parsed_value(ctx, value):
    assert ctx["parsed"] == (None if value == "none" else int(value))
