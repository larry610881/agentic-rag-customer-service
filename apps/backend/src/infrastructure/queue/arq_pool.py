"""arq task queue — enqueue helper for background jobs.

Usage:
    from src.infrastructure.queue.arq_pool import enqueue
    await enqueue("process_document", doc_id, task_id)
"""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

_pool: ArqRedis | None = None


async def get_arq_pool(redis_url: str) -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(redis_url))
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
