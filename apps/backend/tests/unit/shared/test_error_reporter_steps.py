"""錯誤回報機制 BDD Step Definitions"""

import asyncio
import dataclasses

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.shared.error_reporter import ErrorContext
from src.infrastructure.logging.error_context import (
    get_captured_error,
    set_captured_error,
)

scenarios("unit/shared/error_reporter.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# --- Scenario: ErrorContext 正確封裝錯誤資訊 ---


@given("一個 HTTP 請求發生例外")
def http_request_error(context):
    context["request_id"] = "abc123"
    context["tenant_id"] = "t-001"
    context["method"] = "POST"
    context["path"] = "/api/v1/bots"
    context["status_code"] = 500


@when("我建立 ErrorContext")
def create_error_context(context):
    context["error_ctx"] = ErrorContext(
        request_id=context["request_id"],
        tenant_id=context["tenant_id"],
        method=context["method"],
        path=context["path"],
        status_code=context["status_code"],
    )


@then("ErrorContext 應包含 request_id, tenant_id, method, path, status_code")
def verify_error_context(context):
    ec = context["error_ctx"]
    assert ec.request_id == "abc123"
    assert ec.tenant_id == "t-001"
    assert ec.method == "POST"
    assert ec.path == "/api/v1/bots"
    assert ec.status_code == 500


# --- Scenario: ErrorContext 是不可變的 ---


@given("一個已建立的 ErrorContext")
def existing_error_context(context):
    context["error_ctx"] = ErrorContext(
        request_id="x",
        tenant_id="t",
        method="GET",
        path="/",
        status_code=200,
    )


@when("我嘗試修改其屬性")
def try_modify(context):
    try:
        context["error_ctx"].request_id = "new"  # type: ignore[misc]
        context["error"] = None
    except dataclasses.FrozenInstanceError as e:
        context["error"] = e


@then("應拋出 FrozenInstanceError")
def verify_frozen(context):
    assert context["error"] is not None
    assert isinstance(context["error"], dataclasses.FrozenInstanceError)


# --- Scenario: ContextVar 可設定與讀取 captured_error ---


@when("我設定 captured_error 為一個錯誤訊息")
def set_error(context):
    set_captured_error("something went wrong")


@then("我應能透過 get_captured_error 讀取該訊息")
def verify_get_error(context):
    assert get_captured_error() == "something went wrong"
    # cleanup
    set_captured_error(None)


# --- Scenario: ContextVar 預設值為 None ---


@when("我在未設定的情況下讀取 captured_error")
def read_default(context):
    # ContextVar has default None
    context["result"] = get_captured_error()


@then("應回傳 None")
def verify_none(context):
    assert context["result"] is None
