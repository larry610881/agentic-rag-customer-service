"""BackgroundTask 錯誤捕捉 wrapper — 最小止血方案。"""

from collections.abc import Awaitable, Callable
from typing import Any

from src.infrastructure.logging.setup import get_logger

logger = get_logger(__name__)


async def safe_background_task(
    coro_fn: Callable[..., Awaitable[Any]],
    *args: Any,
    task_name: str = "",
    **context: Any,
) -> None:
    """包裝 async callable，捕捉例外並記錄 structured log。

    用法::

        background_tasks.add_task(
            safe_background_task,
            use_case.execute, events,
            task_name="handle_webhook",
        )
    """
    resolved_name = task_name or getattr(coro_fn, "__qualname__", str(coro_fn))
    try:
        await coro_fn(*args)
    except Exception:
        logger.exception(
            "background_task_failed",
            task_name=resolved_name,
            **context,
        )
