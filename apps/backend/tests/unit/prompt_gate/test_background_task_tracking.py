"""Regression: 背景任務引用被保存直到完成（M4）。"""

import asyncio

from src.application.prompt_gate._background import (
    _BACKGROUND_TASKS,
    spawn_tracked,
)


def test_task_reference_held_until_done_and_exception_logged():
    async def _scenario():
        started = asyncio.Event()
        release = asyncio.Event()

        async def _work():
            started.set()
            await release.wait()

        t = spawn_tracked(_work(), name="unit-test")
        await started.wait()
        # 執行中：引用被保存（不會被 GC）
        assert t in _BACKGROUND_TASKS
        release.set()
        await t
        # 完成後：從 set 移除
        assert t not in _BACKGROUND_TASKS

    asyncio.new_event_loop().run_until_complete(_scenario())


def test_failing_task_removed_and_does_not_raise():
    async def _scenario():
        async def _boom():
            raise RuntimeError("boom")

        t = spawn_tracked(_boom(), name="boom")
        # done callback 取出 exception（不外拋），最終從 set 移除
        try:
            await t
        except RuntimeError:
            pass
        await asyncio.sleep(0)  # 讓 done callback 執行
        assert t not in _BACKGROUND_TASKS

    asyncio.new_event_loop().run_until_complete(_scenario())
