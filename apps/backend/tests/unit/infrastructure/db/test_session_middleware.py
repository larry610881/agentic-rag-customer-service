"""SessionCleanupMiddleware / independent_session_scope（pool leak 紅線）。

全域 CLAUDE.md：session 必須在「同一個 async task」內建立與清理，否則
ContextVar 隔離 → session 永不 close → idle in transaction → pool 耗盡。
這裡守：成功 / 例外 / 非 http scope / rollback 失敗 / close 失敗（invalidate 兜底）
各路徑都會釋放連線，且清理後 ContextVar 還原、不外洩到下一個請求。
"""

import asyncio

import pytest

from src.infrastructure.db import session_middleware as sm


class _FakeSession:
    def __init__(
        self,
        *,
        in_tx: bool = True,
        rollback_fails: bool = False,
        close_fails: bool = False,
        invalidate_fails: bool = False,
    ) -> None:
        self.in_tx = in_tx
        self.rollback_fails = rollback_fails
        self.close_fails = close_fails
        self.invalidate_fails = invalidate_fails
        self.calls: list[str] = []

    def in_transaction(self) -> bool:
        return self.in_tx

    async def rollback(self) -> None:
        self.calls.append("rollback")
        if self.rollback_fails:
            raise RuntimeError("rollback failed")

    async def close(self) -> None:
        self.calls.append("close")
        if self.close_fails:
            raise RuntimeError("close failed")

    async def invalidate(self) -> None:
        self.calls.append("invalidate")
        if self.invalidate_fails:
            raise RuntimeError("invalidate failed")


@pytest.fixture
def factory(monkeypatch):
    """替換 session factory；回傳已建立的 session 清單與下一個 session 設定。"""
    state: dict = {"created": [], "kwargs": {}}

    def _make():
        s = _FakeSession(**state["kwargs"])
        state["created"].append(s)
        return s

    monkeypatch.setattr(sm, "async_session_factory", _make)
    return state


async def _noop_receive():
    return {"type": "http.request"}


def _run_mw(app, scope_type: str = "http"):
    sent: list = []

    async def send(msg):
        sent.append(msg)

    async def main():
        await sm.SessionCleanupMiddleware(app)(
            {"type": scope_type, "path": "/"}, _noop_receive, send
        )

    asyncio.run(main())
    return sent


def _app_using_session(times: int = 1, raise_exc: Exception | None = None):
    seen: list = []

    async def app(scope, receive, send):
        for _ in range(times):
            seen.append(sm.get_tracked_session())
        await send({"type": "http.response.start", "status": 200})
        if raise_exc is not None:
            raise raise_exc

    return app, seen


def test_http_request_session_is_singleton_and_closed(factory):
    app, seen = _app_using_session(times=3)
    _run_mw(app)
    assert len(factory["created"]) == 1
    assert seen[0] is seen[1] is seen[2]
    assert factory["created"][0].calls == ["rollback", "close"]
    # 清理後 ContextVar 還原，不會把舊 session 帶給下一個請求
    assert sm._request_session.get() is None


def test_http_request_without_open_transaction_only_closes(factory):
    factory["kwargs"] = {"in_tx": False}
    app, _ = _app_using_session()
    _run_mw(app)
    assert factory["created"][0].calls == ["close"]


def test_http_request_that_never_touches_db_creates_no_session(factory):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 204})

    _run_mw(app)
    assert factory["created"] == []


def test_app_exception_still_closes_session_and_propagates(factory):
    app, _ = _app_using_session(raise_exc=ValueError("boom"))
    with pytest.raises(ValueError, match="boom"):
        _run_mw(app)
    assert factory["created"][0].calls == ["rollback", "close"]
    assert sm._request_session.get() is None


def test_rollback_failure_does_not_skip_close(factory):
    factory["kwargs"] = {"rollback_fails": True}
    app, _ = _app_using_session()
    _run_mw(app)
    assert factory["created"][0].calls == ["rollback", "close"]


def test_close_failure_invalidates_connection(factory):
    factory["kwargs"] = {"close_fails": True}
    app, _ = _app_using_session()
    _run_mw(app)
    assert factory["created"][0].calls == ["rollback", "close", "invalidate"]


def test_invalidate_failure_is_swallowed(factory):
    factory["kwargs"] = {"close_fails": True, "invalidate_fails": True}
    app, _ = _app_using_session()
    sent = _run_mw(app)
    assert sent[0]["status"] == 200
    assert factory["created"][0].calls == ["rollback", "close", "invalidate"]


@pytest.mark.parametrize("scope_type", ["websocket", "lifespan"])
def test_non_http_scope_passes_through_without_session_handling(
    factory, scope_type
):
    calls: list = []

    async def app(scope, receive, send):
        calls.append(scope["type"])

    _run_mw(app, scope_type=scope_type)
    assert calls == [scope_type]
    assert factory["created"] == []


def test_concurrent_requests_get_separate_sessions(factory):
    """兩個同時進行的請求各拿自己的 session，各自關閉。"""
    gate = asyncio.Event()
    seen: dict[str, object] = {}

    async def app(scope, receive, send):
        seen[scope["path"]] = sm.get_tracked_session()
        if scope["path"] == "/a":
            await gate.wait()
        else:
            gate.set()

    async def send(msg):
        pass

    async def main():
        mw = sm.SessionCleanupMiddleware(app)
        await asyncio.gather(
            mw({"type": "http", "path": "/a"}, _noop_receive, send),
            mw({"type": "http", "path": "/b"}, _noop_receive, send),
        )

    asyncio.run(main())
    assert seen["/a"] is not seen["/b"]
    assert all(s.calls == ["rollback", "close"] for s in factory["created"])


# ------------------------------------------------------ independent scope


def test_independent_scope_uses_new_session_and_restores_request_session(factory):
    async def main():
        request_session = sm.get_tracked_session()
        async with sm.independent_session_scope():
            bg = sm.get_tracked_session()
            assert bg is not request_session
        # 背景 session 已關，request session 未被動到且仍可取得
        assert bg.calls == ["rollback", "close"]
        assert request_session.calls == []
        assert sm.get_tracked_session() is request_session

    asyncio.run(main())


def test_independent_scope_without_db_use_is_noop(factory):
    async def main():
        async with sm.independent_session_scope():
            pass

    asyncio.run(main())
    assert factory["created"] == []


def test_independent_scope_cleans_up_on_exception_and_failures(factory):
    factory["kwargs"] = {"rollback_fails": True, "close_fails": True}

    async def main():
        with pytest.raises(KeyError):
            async with sm.independent_session_scope():
                sm.get_tracked_session()
                raise KeyError("x")

    asyncio.run(main())
    assert factory["created"][0].calls == ["rollback", "close"]
