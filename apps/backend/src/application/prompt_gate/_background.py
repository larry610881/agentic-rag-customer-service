"""背景任務引用管理（M4）。

CPython 官方文件明載：asyncio.create_task 的回傳值必須自行保存，否則 task 可能在
執行中被 GC 直接消失——無 exception、無 log、except 不執行 → gate/replay run 永停
running、版本永卡 validating（無法再 validate/publish/reject）。此模組保存強引用直到
任務結束，並在 done callback 取出 exception 讓其浮現到 log。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)

_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


def spawn_tracked(coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task[Any]:
    """建立背景任務並保存強引用直到完成；done 時記錄未處理的例外。"""
    task = asyncio.create_task(coro, name=name)
    _BACKGROUND_TASKS.add(task)

    def _done(t: asyncio.Task[Any]) -> None:
        _BACKGROUND_TASKS.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            logger.error(
                "background task %s failed", name, exc_info=exc
            )

    task.add_done_callback(_done)
    return task
