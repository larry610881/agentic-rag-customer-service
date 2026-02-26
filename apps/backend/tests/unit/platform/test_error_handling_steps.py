"""BackgroundTask 錯誤捕捉 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.logging.error_handler import safe_background_task

scenarios("unit/platform/error_handling.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture
def context():
    return {}


@given("一個會拋出例外的 async 任務")
def setup_failing_task(context):
    async def failing_task():
        raise RuntimeError("something went wrong")

    context["task_fn"] = failing_task


@given("一個正常完成的 async 任務")
def setup_success_task(context):
    context["task_fn"] = AsyncMock(return_value=None)


@when("透過 safe_background_task 執行該任務")
def execute_safe_background_task(context):
    with patch(
        "src.infrastructure.logging.error_handler.logger"
    ) as mock_logger:
        context["mock_logger"] = mock_logger
        _run(
            safe_background_task(
                context["task_fn"],
                task_name="test_task",
            )
        )


@then("例外應被捕捉且不向外傳播")
def verify_no_exception_propagated(context):
    # If we reached here, the exception was caught
    pass


@then("結構化日誌應包含 task_name 與 error 資訊")
def verify_structured_log(context):
    context["mock_logger"].exception.assert_called_once()
    call_kwargs = context["mock_logger"].exception.call_args
    assert call_kwargs[0][0] == "background_task_failed"
    assert call_kwargs[1]["task_name"] == "test_task"


@then("任務應正常完成")
def verify_task_completed(context):
    context["task_fn"].assert_awaited_once()


@then("不應有錯誤日誌產生")
def verify_no_error_log(context):
    context["mock_logger"].exception.assert_not_called()
