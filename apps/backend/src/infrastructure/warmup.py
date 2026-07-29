"""換版啟動暖機 — Issue #53

Cloud Run 已設 min-instances=1（無 scale-to-zero），但每次部署換版後
新容器的 DB 連線池 / Milvus client / Redis 連線全是冷的，首請求付
~5-9s 暖機成本（#52 實測首則 9.1s）。

uvicorn 在 lifespan startup 完成後才開始接受連線 → 把暖機放在
lifespan 內，Cloud Run startup probe（TCP）自然等暖機完成才切流量，
期間舊 revision 繼續服務，使用者無感。

Fail-open：任一探測失敗只記 warning；整體逾時上限保護 —— 外部服務
故障絕不能讓容器起不來（部署卡死比首請求慢嚴重得多）。
"""

import asyncio
import time
from typing import Any

from sqlalchemy import text

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 15.0


async def _probe(name: str, coro) -> None:
    start = time.perf_counter()
    try:
        await coro
        logger.info(
            "startup_warmup.probe_ok",
            target=name,
            elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
        )
    except Exception:
        logger.warning(
            "startup_warmup.probe_failed",
            target=name,
            elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
            exc_info=True,
        )


async def _probe_db(session_factory: Any) -> None:
    async with session_factory() as session:
        await session.execute(text("SELECT 1"))


async def run_startup_warmup(
    *,
    session_factory: Any,
    vector_store: Any,
    cache_service: Any,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """並行預熱 DB / Milvus / Redis 連線；永不拋例外。"""
    start = time.perf_counter()
    try:
        await asyncio.wait_for(
            asyncio.gather(
                _probe("db", _probe_db(session_factory)),
                _probe("milvus", vector_store.ping()),
                _probe("redis", cache_service.get("warmup:ping")),
            ),
            timeout=timeout_seconds,
        )
    except (TimeoutError, asyncio.TimeoutError):
        logger.warning(
            "startup_warmup.timeout", timeout_seconds=timeout_seconds
        )
    except Exception:  # 防禦性 — 暖機任何失敗都不得擋啟動
        logger.warning("startup_warmup.failed", exc_info=True)
    logger.info(
        "startup_warmup.done",
        elapsed_ms=round((time.perf_counter() - start) * 1000, 1),
    )
