"""Usage API Integration — BDD Step Definitions."""

import asyncio
import uuid

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

scenarios("integration/usage/usage_api.feature")

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/agentic_rag_test"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {}


def _create_tenant_and_login(create_tenant_login, name: str) -> dict:
    return create_tenant_login(name)


def _auth_only(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('已登入為租戶 "{name}"'))
def login_as_tenant(ctx, create_tenant_login, name):
    ctx["headers"] = _create_tenant_and_login(create_tenant_login, name)


@given("已有用量紀錄")
def insert_usage_record(ctx):
    tenant_id = ctx["headers"]["_tenant_id"]

    async def _insert():
        eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with eng.begin() as conn:
            # S-Token-Gov.6: total_tokens 已改為 @property 動態算，不再存 DB
            # cache_read_tokens / cache_creation_tokens 必填（S-LLM-Cache.1 新增）
            await conn.execute(
                text(
                    "INSERT INTO token_usage_records "
                    "(id, tenant_id, request_type, model, "
                    "input_tokens, output_tokens, "
                    "cache_read_tokens, cache_creation_tokens, "
                    "estimated_cost, created_at) "
                    "VALUES (:id, :tid, 'rag', 'gpt-4o', "
                    "100, 200, 0, 0, 0.05, now())"
                ),
                {"id": str(uuid.uuid4()), "tid": tenant_id},
            )
        await eng.dispose()

    _run(_insert())


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("我送出認證 GET /api/v1/usage")
def get_usage(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/usage", headers=_auth_only(ctx["headers"])
    )


@when("我不帶 token 送出 GET /api/v1/usage")
def get_usage_no_auth(ctx, client):
    ctx["response"] = client.get("/api/v1/usage")


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then(parsers.parse("用量 total_tokens 為 {count:d}"))
def check_total_tokens_exact(ctx, count):
    body = ctx["response"].json()
    assert body["total_tokens"] == count


@then("用量 total_tokens 大於 0")
def check_total_tokens_positive(ctx):
    body = ctx["response"].json()
    assert body["total_tokens"] > 0
