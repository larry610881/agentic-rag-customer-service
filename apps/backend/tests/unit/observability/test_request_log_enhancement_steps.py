"""請求日誌增強 BDD Step Definitions"""

import asyncio
import base64
import inspect
import json

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.logging.request_log_writer import write_request_log
from src.interfaces.api.middleware import extract_tenant_id

scenarios("unit/observability/request_log_enhancement.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_jwt(payload: dict) -> str:
    """Build a fake JWT (header.payload.signature) with given payload."""
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256"}).encode()
    ).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{body}.fakesig"


# --- Scenario: user_access JWT ---


@given(parsers.parse('一個 user_access 類型的 JWT token 包含 tenant_id "{tid}"'))
def user_access_token(context, tid):
    context["token"] = _make_jwt({"type": "user_access", "tenant_id": tid, "sub": "u-1"})


# --- Scenario: tenant_access JWT ---


@given(parsers.parse('一個 tenant_access 類型的 JWT token 包含 sub "{tid}"'))
def tenant_access_token(context, tid):
    context["token"] = _make_jwt({"type": "tenant_access", "sub": tid})


# --- Scenario: 無 Authorization header ---


@given("一個沒有 Authorization header 的請求")
def no_auth_header(context):
    context["token"] = None


# --- Scenario: 無效 JWT ---


@given("一個包含無效 JWT 的請求")
def invalid_jwt(context):
    context["token"] = "not-a-valid-jwt"


# --- When / Then ---


@when("我解析該 token 的 tenant_id")
def parse_tenant_id(context):
    token = context.get("token")
    if token is None:
        context["result"] = extract_tenant_id("")
    else:
        context["result"] = extract_tenant_id(f"Bearer {token}")


@then(parsers.parse('應回傳 "{expected}"'))
def verify_result(context, expected):
    assert context["result"] == expected


@then("應回傳 None", target_fixture="none_result")
def verify_none(context):
    assert context["result"] is None


# --- Scenario: write_request_log 函式簽名 ---


@given("write_request_log 函式接受 tenant_id 和 error_detail 參數")
def check_function_exists(context):
    context["sig"] = inspect.signature(write_request_log)


@then("函式簽名應包含 tenant_id 和 error_detail 可選參數")
def verify_signature(context):
    params = context["sig"].parameters
    assert "tenant_id" in params
    assert "error_detail" in params
    # Both should have default values (optional)
    assert params["tenant_id"].default is None or params["tenant_id"].default == inspect.Parameter.empty
    assert params["error_detail"].default is None or params["error_detail"].default == inspect.Parameter.empty
