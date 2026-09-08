"""arq task queue — enqueue helper for background jobs.

Usage:
    from src.infrastructure.queue.arq_pool import enqueue
    await enqueue("process_document", doc_id, task_id)
"""

from urllib.parse import unquote, urlparse

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

_pool: ArqRedis | None = None

#: queue_depth 掃描上限——只需分辨「0 / 非 0」，不必拉回整個佇列
_QUEUE_SCAN_LIMIT = 500


def _parse_redis_settings(url: str) -> RedisSettings:
    """Parse Redis URL with proper password URL-decoding."""
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=unquote(parsed.password) if parsed.password else None,
        database=int(parsed.path.lstrip("/") or 0),
    )


async def get_arq_pool(redis_url: str) -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(_parse_redis_settings(redis_url))
    return _pool


async def enqueue(job_name: str, *args: object) -> str | None:
    """Enqueue a job to arq. Returns job ID or None on failure."""
    from src.config import Settings

    try:
        pool = await get_arq_pool(Settings().redis_url)
        job = await pool.enqueue_job(job_name, *args)
        if job:
            logger.info("arq.enqueued", job_name=job_name, job_id=job.job_id)
            return job.job_id
        logger.warning("arq.enqueue_skipped", job_name=job_name)
        return None
    except Exception:
        logger.exception("arq.enqueue_failed", job_name=job_name)
        return None


async def queue_depth(redis_url: str) -> int:
    """佇列裡還沒被撿走的**業務**工作數（含等待重試的 deferred）。

    reaper 用它來分辨「排隊中」與「派工遺失」：worker 一撿到工作就會把文件轉成
    ``processing``，所以佇列見底時仍是 ``pending`` 的文件，它的工作根本不存在。

    **不能直接用 ZCARD**：arq 把 cron 也放進同一個 sorted set，而本專案有兩支
    每分鐘的 cron（conversation_summary_scan、drain_outbox），於是 ZCARD 幾乎
    永遠 > 0，「見底」這個判準會永遠不成立、安全網形同虛設（2026-09-08 首次
    上線就是這樣，log 顯示 queue_depth=2、skipped=3）。cron 的 job id 一律是
    ``cron:<name>:<ms>``，據此濾掉。

    deferred（未來才到期的重試）**刻意計入**：那是真的還在跑的工作，把它當成
    「佇列空了」會誤殺正在重試的文件。

    探測失敗回 ``-1``（未知），呼叫端據此走保守路徑、不誤判。
    """
    try:
        pool = await get_arq_pool(redis_url)
        name = getattr(pool, "default_queue_name", "arq:queue")
        # 只要知道「有沒有積壓」，不必把整個佇列拉回來
        members = await pool.zrange(name, 0, _QUEUE_SCAN_LIMIT - 1)
        return sum(
            1
            for m in members
            if not (
                m.decode() if isinstance(m, bytes) else str(m)
            ).startswith("cron:")
        )
    except Exception:
        logger.exception("arq.queue_depth_failed")
        return -1
