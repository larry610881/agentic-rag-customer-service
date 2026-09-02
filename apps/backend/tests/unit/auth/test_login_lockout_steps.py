"""登入失敗鎖定 BDD Step Definitions（Issue #58）"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.auth.login_use_case import (
    AccountLockedError,
    AuthenticationError,
    LoginCommand,
    LoginUseCase,
)
from src.domain.auth.entity import User
from src.domain.auth.login_attempt_tracker import LoginLockoutPolicy
from src.domain.auth.value_objects import Email, Role, UserId
from src.infrastructure.auth.redis_login_attempt_tracker import (
    RedisLoginAttemptTracker,
)
from src.interfaces.api.auth_router import LoginRequest, login

scenarios("unit/auth/login_lockout.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_user_repo():
    return AsyncMock()


@pytest.fixture
def mock_password_service():
    svc = MagicMock()
    svc.verify_password = MagicMock(return_value=True)
    return svc


@pytest.fixture
def mock_jwt_service():
    svc = MagicMock()
    svc.create_user_token = MagicMock(return_value="jwt-token-123")
    svc.create_refresh_token = MagicMock(return_value="refresh-token-456")
    return svc


@pytest.fixture
def mock_tracker():
    tracker = AsyncMock()
    tracker.retry_after = AsyncMock(return_value=0)
    tracker.record_failure = AsyncMock(return_value=0)
    tracker.reset = AsyncMock()
    return tracker


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.ttl = AsyncMock(return_value=-2)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
    return redis


def _build_use_case(context, mock_user_repo, mock_password_service,
                    mock_jwt_service, mock_tracker):
    tracker = None if context.get("no_tracker") else mock_tracker
    return LoginUseCase(
        user_repository=mock_user_repo,
        password_service=mock_password_service,
        jwt_service=mock_jwt_service,
        login_attempt_tracker=tracker,
    )


# ── Background ──


@given(parsers.parse("登入鎖定政策為最多 {max_failures:d} 次失敗、鎖定 {lockout:d} 秒"))
def lockout_policy(context, max_failures, lockout):
    context["policy"] = LoginLockoutPolicy(
        max_failures=max_failures,
        failure_window_seconds=900,
        lockout_seconds=lockout,
    )


# ── Use case givens ──


@given(parsers.parse('已註冊使用者 email "{email}" 角色 "{role}" 租戶 "{tenant_id}"'))
def registered_user(mock_user_repo, mock_password_service, email, role, tenant_id):
    user = User(
        id=UserId(value="user-001"),
        tenant_id=tenant_id,
        email=Email(email),
        hashed_password="hashed_correct",
        role=Role(role),
    )
    mock_user_repo.find_by_email = AsyncMock(return_value=user)
    mock_password_service.verify_password = MagicMock(return_value=True)


@given(parsers.parse('系統中無 email 為 "{email}" 的使用者'))
def no_user(mock_user_repo, email):
    mock_user_repo.find_by_email = AsyncMock(return_value=None)


@given(parsers.parse('帳號 "{email}" 已被鎖定剩餘 {seconds:d} 秒'))
def account_locked(mock_tracker, email, seconds):
    mock_tracker.retry_after = AsyncMock(return_value=seconds)


@given(parsers.parse('帳號 "{email}" 已失敗 {count:d} 次'))
def account_failed_times(context, mock_tracker, email, count):
    policy = context["policy"]
    # 下一次失敗達上限 → tracker 回傳鎖定秒數
    next_locks = count + 1 >= policy.max_failures
    mock_tracker.record_failure = AsyncMock(
        return_value=policy.lockout_seconds if next_locks else 0
    )


@given("未注入登入嘗試追蹤器")
def no_tracker(context):
    context["no_tracker"] = True


# ── Use case when/then ──


@when(parsers.parse('我以 email "{email}" 密碼 "{password}" 登入'))
def do_login(context, mock_user_repo, mock_password_service, mock_jwt_service,
             mock_tracker, email, password):
    if password == "WrongPassword":
        mock_password_service.verify_password = MagicMock(return_value=False)
    use_case = _build_use_case(
        context, mock_user_repo, mock_password_service, mock_jwt_service,
        mock_tracker,
    )
    command = LoginCommand(email=email, password=password)
    try:
        context["result"] = _run(use_case.execute(command))
        context["error"] = None
    except (AuthenticationError, AccountLockedError) as e:
        context["result"] = None
        context["error"] = e


@then(parsers.parse("應拋出帳號鎖定錯誤且 retry_after 為 {seconds:d}"))
def locked_error(context, seconds):
    assert isinstance(context["error"], AccountLockedError), context["error"]
    assert context["error"].retry_after == seconds


@then("不應驗證密碼")
def password_not_verified(mock_password_service, mock_user_repo):
    mock_password_service.verify_password.assert_not_called()
    mock_user_repo.find_by_email.assert_not_called()


@then("應拋出認證失敗錯誤")
def auth_error(context):
    assert isinstance(context["error"], AuthenticationError), context["error"]


@then("應記錄一次登入失敗")
def failure_recorded(mock_tracker):
    mock_tracker.record_failure.assert_awaited_once()


@then("應回傳包含 user_id 和 tenant_id 和 role 的 JWT")
def jwt_returned(context):
    assert context["result"] is not None
    assert context["result"].access_token == "jwt-token-123"


@then(parsers.parse('應清除帳號 "{email}" 的失敗計數'))
def failures_reset(mock_tracker, email):
    mock_tracker.reset.assert_awaited_once_with(email)
    mock_tracker.record_failure.assert_not_awaited()


@then(parsers.parse('應以識別 "{identifier}" 記錄登入失敗'))
def failure_recorded_with_identifier(mock_tracker, identifier):
    mock_tracker.record_failure.assert_awaited_once_with(identifier)


# ── Router ──


@given(parsers.parse("LoginUseCase 拋出 AccountLockedError retry_after {seconds:d}"))
def uc_raises_locked(context, seconds):
    mock_uc = AsyncMock()
    mock_uc.execute = AsyncMock(side_effect=AccountLockedError(seconds))
    context["login_use_case"] = mock_uc


@when(parsers.parse('我透過 login API 以 account "{account}" 密碼 "{password}" 登入'))
def call_login_api(context, account, password):
    mock_jwt = MagicMock()
    mock_tenant_repo = AsyncMock()
    mock_tenant_repo.find_by_name = AsyncMock(return_value=None)
    body = LoginRequest(account=account, password=password)
    with patch("src.interfaces.api.auth_router.settings") as mock_settings:
        mock_settings.app_env = "production"
        try:
            _run(login(
                body=body,
                jwt_service=mock_jwt,
                tenant_repo=mock_tenant_repo,
                use_case=context["login_use_case"],
            ))
            context["api_error"] = None
        except Exception as e:  # noqa: BLE001
            context["api_error"] = e


@then(parsers.parse('應拋出 HTTP {code:d} 錯誤且 Retry-After 為 "{value}"'))
def api_locked(context, code, value):
    err = context["api_error"]
    assert isinstance(err, HTTPException), err
    assert err.status_code == code
    assert err.headers is not None and err.headers.get("Retry-After") == value


@then("錯誤訊息不應透露帳號是否存在")
def api_error_generic(context):
    detail = str(context["api_error"].detail).lower()
    assert "user@example.com" not in detail
    assert "not found" not in detail and "exist" not in detail


# ── Redis tracker ──


def _tracker(context, mock_redis):
    return RedisLoginAttemptTracker(
        redis_client=mock_redis, policy=context["policy"]
    )


@given("Redis 中鎖定 key 不存在")
def redis_no_lock(mock_redis):
    mock_redis.ttl = AsyncMock(return_value=-2)


@given(parsers.parse("Redis 失敗計數 INCR 後為 {count:d}"))
def redis_incr_returns(mock_redis, count):
    mock_redis.incr = AsyncMock(return_value=count)


@given("Redis 連線拋出例外")
def redis_raises(mock_redis):
    mock_redis.ttl = AsyncMock(side_effect=ConnectionError("down"))
    mock_redis.incr = AsyncMock(side_effect=ConnectionError("down"))


@when(parsers.parse('查詢帳號 "{email}" 的 retry_after'))
def query_retry_after(context, mock_redis, email):
    context["retry_after"] = _run(_tracker(context, mock_redis).retry_after(email))


@when(parsers.parse('記錄帳號 "{email}" 一次登入失敗'))
def record_failure(context, mock_redis, email):
    context["record_result"] = _run(
        _tracker(context, mock_redis).record_failure(email)
    )


@then(parsers.parse("retry_after 應為 {seconds:d}"))
def retry_after_is(context, seconds):
    assert context["retry_after"] == seconds


@then(parsers.parse("應以 {ttl:d} 秒 TTL 建立鎖定 key"))
def lock_key_created(mock_redis, ttl):
    mock_redis.set.assert_awaited_once()
    args, kwargs = mock_redis.set.call_args
    assert args[0] == "login:lock:user@example.com"
    assert kwargs.get("ex") == ttl


@then("應清除失敗計數 key")
def fail_key_deleted(mock_redis):
    mock_redis.delete.assert_awaited_with("login:fail:user@example.com")


@then("不應建立鎖定 key")
def lock_key_not_created(mock_redis):
    mock_redis.set.assert_not_awaited()
    mock_redis.expire.assert_awaited_once()


@then(parsers.parse("回傳的 retry_after 應為 {seconds:d}"))
def record_result_is(context, seconds):
    assert context["record_result"] == seconds


# Unused-but-required fixture references for SimpleNamespace import parity
_ = SimpleNamespace
