"""Redis 版異常分數儲存（Issue #68 P7a）

key：
- ``{key}``（hash score/ts）：線性衰減分數，Lua 原子更新
- ``{key}:lvl``：等級鎖，TTL = 持續時間
- ``{key}:rpm`` / ``{key}:pacing_flag`` / ``{key}:unrouted``：計數器

失效時直接丟例外，由 AbuseControlService fail-open。
"""

import time

from src.domain.abuse.store import AbuseScoreStore

# 衰減後加分並續 TTL；回傳新分數
_ADD_LUA = """
local s = redis.call('HMGET', KEYS[1], 'score', 'ts')
local now = tonumber(ARGV[1])
local score = tonumber(s[1]) or 0
local ts = tonumber(s[2]) or now
local decay = tonumber(ARGV[2])
local delta = tonumber(ARGV[3])
score = math.max(0, score - decay * (now - ts) / 60) + delta
redis.call('HSET', KEYS[1], 'score', score, 'ts', now)
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[4]))
return tostring(score)
"""


class RedisAbuseScoreStore(AbuseScoreStore):
    def __init__(self, redis_client) -> None:  # noqa: ANN001
        self._redis = redis_client

    async def add_score(
        self, key: str, delta: float, decay_per_minute: float, ttl_seconds: int
    ) -> float:
        raw = await self._redis.eval(
            _ADD_LUA, 1, key, time.time(), decay_per_minute, delta, ttl_seconds
        )
        return float(raw.decode() if isinstance(raw, bytes) else raw)

    async def get_score(self, key: str, decay_per_minute: float) -> float:
        score_raw, ts_raw = await self._redis.hmget(key, "score", "ts")
        if score_raw is None:
            return 0.0
        score = float(score_raw.decode() if isinstance(score_raw, bytes) else score_raw)
        ts = float(ts_raw.decode() if isinstance(ts_raw, bytes) else ts_raw or 0)
        return max(0.0, score - decay_per_minute * (time.time() - ts) / 60.0)

    async def set_level(self, key: str, level: int, ttl_seconds: int) -> None:
        await self._redis.set(f"{key}:lvl", str(level), ex=ttl_seconds)

    async def get_level(self, key: str) -> tuple[int, int] | None:
        raw = await self._redis.get(f"{key}:lvl")
        if raw is None:
            return None
        ttl = await self._redis.ttl(f"{key}:lvl")
        level = int(raw.decode() if isinstance(raw, bytes) else raw)
        return level, max(1, int(ttl or 0))

    async def clear(self, key: str) -> None:
        await self._redis.delete(key, f"{key}:lvl")

    async def incr_counter(self, key: str, ttl_seconds: int) -> int:
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, ttl_seconds)
        return int(count)

    async def reset_counter(self, key: str) -> None:
        await self._redis.delete(key)
