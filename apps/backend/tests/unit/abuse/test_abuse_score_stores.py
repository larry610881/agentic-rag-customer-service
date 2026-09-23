"""異常分數儲存（Redis 版以 fakeredis、記憶體版以注入時鐘；Issue #101 B8）。

守：分數線性衰減（讀取端）、等級鎖 TTL 與剩餘秒數、計數器首次才設 TTL（不被
續命）、clear 只清該主體、list_locked 只列指定前綴且略過已過期。

add_score 的 _ADD_LUA（fakeredis[lua] 執行）：衰減後加分、續 TTL、不為負、
主體互不影響，且寫入格式與讀取端 get_score 一致。
"""

import asyncio

import fakeredis
import pytest

from src.infrastructure.abuse import redis_abuse_score_store as rmod
from src.infrastructure.abuse.in_memory_abuse_score_store import (
    InMemoryAbuseScoreStore,
)
from src.infrastructure.abuse.redis_abuse_score_store import RedisAbuseScoreStore

_K = "abuse:t1:visitor:v1"


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def now(monkeypatch):
    t = [1_000_000.0]
    monkeypatch.setattr(rmod.time, "time", lambda: t[0])
    return t


# ------------------------------------------------------------------ redis


def test_redis_get_score_absent_is_zero(now):
    s = RedisAbuseScoreStore(fakeredis.FakeAsyncRedis())
    assert _run(s.get_score(_K, 1.0)) == 0.0


def test_redis_get_score_decays_linearly_and_floors_at_zero(now):
    r = fakeredis.FakeAsyncRedis()
    s = RedisAbuseScoreStore(r)

    async def main():
        await r.hset(_K, mapping={"score": 10, "ts": now[0]})
        assert await s.get_score(_K, 2.0) == pytest.approx(10.0)
        now[0] += 120  # 2 分鐘 × 2/分 = 衰減 4
        assert await s.get_score(_K, 2.0) == pytest.approx(6.0)
        now[0] += 600
        assert await s.get_score(_K, 2.0) == 0.0  # 不會變負

    _run(main())


def test_redis_get_score_str_responses(now):
    r = fakeredis.FakeAsyncRedis(decode_responses=True)
    s = RedisAbuseScoreStore(r)

    async def main():
        await r.hset(_K, mapping={"score": "3.5", "ts": str(now[0] - 60)})
        assert await s.get_score(_K, 1.0) == pytest.approx(2.5)

    _run(main())


def test_redis_level_lock_ttl_and_clear():
    r = fakeredis.FakeAsyncRedis()
    s = RedisAbuseScoreStore(r)

    async def main():
        assert await s.get_level(_K) is None
        await s.set_level(_K, 3, 600)
        level, remaining = await s.get_level(_K)
        assert level == 3 and 0 < remaining <= 600
        await r.hset(_K, mapping={"score": 5, "ts": 0})
        other = "abuse:t1:visitor:v2"
        await s.set_level(other, 2, 600)

        await s.clear(_K)
        assert await s.get_level(_K) is None
        assert await r.exists(_K) == 0
        assert (await s.get_level(other))[0] == 2  # 其他主體不受影響

    _run(main())


def test_redis_counter_ttl_set_only_on_first_increment():
    r = fakeredis.FakeAsyncRedis()
    s = RedisAbuseScoreStore(r)
    key = "abuse:t1:visitor:v1:rpm"

    async def main():
        assert await s.incr_counter(key, 60) == 1
        assert 0 < await r.ttl(key) <= 60
        await r.expire(key, 5)  # 模擬時間流逝
        assert await s.incr_counter(key, 60) == 2
        assert await r.ttl(key) <= 5  # 固定視窗：後續 incr 不續命
        await s.reset_counter(key)
        assert await r.exists(key) == 0

    _run(main())


def test_redis_list_locked_filters_by_prefix():
    r = fakeredis.FakeAsyncRedis()
    s = RedisAbuseScoreStore(r)

    async def main():
        await s.set_level("abuse:t1:visitor:a", 2, 300)
        await s.set_level("abuse:t1:user:b", 4, 300)
        await s.set_level("abuse:t2:visitor:c", 3, 300)
        got = sorted(await s.list_locked("abuse:t1:"))
        assert [(k, lvl) for k, lvl, _ in got] == [
            ("abuse:t1:user:b", 4),
            ("abuse:t1:visitor:a", 2),
        ]
        assert all(0 < ttl <= 300 for _, _, ttl in got)

    _run(main())


class _EvalStub:
    def __init__(self, result) -> None:
        self.result = result
        self.args: tuple = ()

    async def eval(self, *args):
        self.args = args
        return self.result


@pytest.mark.parametrize("raw", [b"7.5", "7.5"])
def test_redis_add_score_argument_order(now, raw):
    stub = _EvalStub(raw)
    got = _run(RedisAbuseScoreStore(stub).add_score(_K, 3.0, 0.5, 900))
    assert got == 7.5
    # KEYS[1]=key；ARGV = now, decay, delta, ttl（對應 _ADD_LUA）
    assert stub.args[1:] == (1, _K, now[0], 0.5, 3.0, 900)


# ------------------------------------------------------------------ memory


def test_memory_score_expires_after_ttl():
    t = [0.0]
    s = InMemoryAbuseScoreStore(clock=lambda: t[0])

    async def main():
        await s.add_score(_K, 5.0, 0.0, 60)
        assert await s.get_score(_K, 0.0) == 5.0
        t[0] = 61
        assert await s.get_score(_K, 0.0) == 0.0

    _run(main())


def test_memory_list_locked_drops_expired_and_other_prefix():
    t = [0.0]
    s = InMemoryAbuseScoreStore(clock=lambda: t[0])

    async def main():
        await s.set_level("abuse:t1:visitor:a", 2, 10)
        await s.set_level("abuse:t1:visitor:b", 3, 100)
        await s.set_level("abuse:t2:visitor:c", 3, 100)
        t[0] = 20
        assert await s.list_locked("abuse:t1:") == [("abuse:t1:visitor:b", 3, 80)]
        # 過期項目已被清掉
        assert await s.get_level("abuse:t1:visitor:a") is None

    _run(main())


# ------------------------------------------------------------ _ADD_LUA（真腳本）


def test_redis_add_score_lua_decay_then_add(now):
    r = fakeredis.FakeAsyncRedis()
    s = RedisAbuseScoreStore(r)

    async def main():
        assert await s.add_score(_K, 10.0, 2.0, 900) == pytest.approx(10.0)
        now[0] += 90  # 1.5 分鐘 × 2/分 = 衰減 3 → 7 + 4
        assert await s.add_score(_K, 4.0, 2.0, 900) == pytest.approx(11.0)
        # 腳本寫入的 ts 以本次時間為基準，讀取端 get_score 與之一致
        assert await s.get_score(_K, 2.0) == pytest.approx(11.0)
        now[0] += 30
        assert await s.get_score(_K, 2.0) == pytest.approx(10.0)

    _run(main())


def test_redis_add_score_lua_fractional_values_preserved(now):
    r = fakeredis.FakeAsyncRedis()
    s = RedisAbuseScoreStore(r)

    async def main():
        await s.add_score(_K, 0.5, 0.25, 900)
        now[0] += 60
        assert await s.add_score(_K, 0.75, 0.25, 900) == pytest.approx(1.0)
        assert await s.get_score(_K, 0.25) == pytest.approx(1.0)

    _run(main())


def test_redis_add_score_lua_never_negative(now):
    r = fakeredis.FakeAsyncRedis()
    s = RedisAbuseScoreStore(r)

    async def main():
        await s.add_score(_K, 5.0, 1.0, 900)
        now[0] += 3600  # 衰減 60 遠大於 5
        assert await s.add_score(_K, 2.0, 1.0, 900) == pytest.approx(2.0)
        # 只衰減不加分：歸零停在 0
        now[0] += 3600
        assert await s.add_score(_K, 0.0, 1.0, 900) == 0.0

    _run(main())


def test_redis_add_score_lua_extends_ttl(now):
    r = fakeredis.FakeAsyncRedis()
    s = RedisAbuseScoreStore(r)

    async def main():
        await s.add_score(_K, 1.0, 0.0, 300)
        assert 0 < await r.ttl(_K) <= 300
        await r.expire(_K, 5)  # 快到期
        await s.add_score(_K, 1.0, 0.0, 300)
        assert await r.ttl(_K) > 5  # 每次加分續 TTL

    _run(main())


def test_redis_add_score_lua_subjects_independent(now):
    r = fakeredis.FakeAsyncRedis()
    s = RedisAbuseScoreStore(r)
    other = "abuse:t2:visitor:v1"  # 同 visitor id、不同租戶

    async def main():
        await s.add_score(_K, 8.0, 0.0, 900)
        assert await s.add_score(other, 1.0, 0.0, 900) == pytest.approx(1.0)
        assert await s.get_score(_K, 0.0) == pytest.approx(8.0)
        assert await s.get_score(other, 0.0) == pytest.approx(1.0)

    _run(main())


def test_redis_add_score_lua_concurrent_adds_not_lost(now):
    r = fakeredis.FakeAsyncRedis()
    s = RedisAbuseScoreStore(r)

    async def main():
        await asyncio.gather(*(s.add_score(_K, 1.0, 0.0, 900) for _ in range(20)))
        assert await s.get_score(_K, 0.0) == pytest.approx(20.0)

    _run(main())
