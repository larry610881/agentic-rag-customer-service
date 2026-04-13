"""Background Task Error Tracking BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.logging.error_handler import safe_background_task

scenarios("unit/platform/background_task_error_tracking.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# --- Given ---


@given("一個會拋出 ValueError 的 async 任務")
def setup_failing_valueerror_task(context):
    async def failing_task():
        raise ValueError("bad input")

    context["task_fn"] = failing_task
    context["task_name"] = "failing_task"
    context["extra_context"] = {}


@given("一個正常完成的 async 追蹤任務")
def setup_success_tracking_task(context):
    context["task_fn"] = AsyncMock(return_value=None)
    context["task_name"] = "success_task"
    context["extra_context"] = {}


@given(parsers.parse('一個會拋出例外的 async 任務且帶有 tenant_id "{tenant_id}"'))
def setup_failing_task_with_tenant(context, tenant_id):
    async def failing_task():
        raise RuntimeError("boom")

    context["task_fn"] = failing_task
    context["task_name"] = "tenant_task"
    context["extra_context"] = {"tenant_id": tenant_id}


# --- When ---


@when("透過 safe_background_task 執行該任務並追蹤錯誤")
def execute_with_error_tracking(context):
    with (
        patch(
            "src.infrastructure.logging.error_handler.logger"
        ),
        patch(
            "src.infrastructure.logging.error_event_writer.write_error_event",
            new_callable=AsyncMock,
        ) as mock_write,
    ):
        context["mock_write_error_event"] = mock_write
        _run(
            safe_background_task(
                context["task_fn"],
                task_name=context["task_name"],
                **context["extra_context"],
            )
        )


# --- Then ---


@then("write_error_event 應被呼叫一次")
def verify_write_called_once(context):
    context["mock_write_error_event"].assert_awaited_once()


@then("write_error_event 不應被呼叫")
def verify_write_not_called(context):
    context["mock_write_error_event"].assert_not_awaited()


@then(parsers.parse('error_detail 應為 "{expected}"'))
def verify_error_detail(context, expected):
    call_kwargs = context["mock_write_error_event"].call_args[1]
    assert call_kwargs["error_detail"] == expected


@then(parsers.parse('method 應為 "{expected}"'))
def verify_method(context, expected):
    call_kwargs = context["mock_write_error_event"].call_args[1]
    assert call_kwargs["method"] == expected


@then(parsers.parse('path 應為 "{expected}"'))
def verify_path(context, expected):
    call_kwargs = context["mock_write_error_event"].call_args[1]
    assert call_kwargs["path"] == expected


@then(parsers.parse("status_code 應為 {code:d}"))
def verify_status_code(context, code):
    call_kwargs = context["mock_write_error_event"].call_args[1]
    assert call_kwargs["status_code"] == code


@then(parsers.parse('tenant_id 應為 "{expected}"'))
def verify_tenant_id(context, expected):
    call_kwargs = context["mock_write_error_event"].call_args[1]
    assert call_kwargs["tenant_id"] == expected
