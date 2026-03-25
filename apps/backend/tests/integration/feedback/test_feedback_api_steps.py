"""Feedback API Integration — BDD Step Definitions."""

import asyncio
import uuid

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

scenarios("integration/feedback/feedback_api.feature")

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


@given("已建立對話和訊息")
def create_conversation_and_message(ctx):
    """Insert conversation + message directly into DB for feedback tests."""
    tenant_id = ctx["headers"]["_tenant_id"]
    conv_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())
    ctx["conversation_id"] = conv_id
    ctx["message_id"] = msg_id

    async def _insert():
        eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with eng.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO conversations (id, tenant_id, created_at) "
                    "VALUES (:cid, :tid, now())"
                ),
                {"cid": conv_id, "tid": tenant_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO messages "
                    "(id, conversation_id, role, content, tool_calls_json, created_at) "
                    "VALUES (:mid, :cid, 'assistant', '測試回覆', '[]', now())"
                ),
                {"mid": msg_id, "cid": conv_id},
            )
        await eng.dispose()

    _run(_insert())
    # Track message counter for multi-feedback scenarios
    ctx["_msg_counter"] = 0


@given(parsers.parse('已提交回饋 "{rating}"'))
def submit_feedback_given(ctx, client, rating):
    """Submit feedback; create a new message each time to avoid uniqueness issues."""
    ctx["_msg_counter"] = ctx.get("_msg_counter", 0) + 1
    new_msg_id = str(uuid.uuid4())

    async def _insert_msg():
        eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with eng.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO messages "
                    "(id, conversation_id, role, content, tool_calls_json, created_at) "
                    "VALUES (:mid, :cid, 'assistant', '回覆', '[]', now())"
                ),
                {"mid": new_msg_id, "cid": ctx["conversation_id"]},
            )
        await eng.dispose()

    _run(_insert_msg())

    resp = client.post(
        "/api/v1/feedback",
        json={
            "conversation_id": ctx["conversation_id"],
            "message_id": new_msg_id,
            "rating": rating,
        },
        headers=_auth_only(ctx["headers"]),
    )
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('我送出 POST /api/v1/feedback 評分為 "{rating}"'))
def post_feedback(ctx, client, rating):
    ctx["response"] = client.post(
        "/api/v1/feedback",
        json={
            "conversation_id": ctx["conversation_id"],
            "message_id": ctx["message_id"],
            "rating": rating,
        },
        headers=_auth_only(ctx["headers"]),
    )


@when(
    parsers.parse(
        '我送出 POST /api/v1/feedback 評分為 "{rating}" 留言 "{comment}"'
    )
)
def post_feedback_with_comment(ctx, client, rating, comment):
    ctx["response"] = client.post(
        "/api/v1/feedback",
        json={
            "conversation_id": ctx["conversation_id"],
            "message_id": ctx["message_id"],
            "rating": rating,
            "comment": comment,
        },
        headers=_auth_only(ctx["headers"]),
    )


@when("我送出認證 GET /api/v1/feedback")
def get_feedback_list(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/feedback", headers=_auth_only(ctx["headers"])
    )


@when("我送出認證 GET /api/v1/feedback/stats")
def get_feedback_stats(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/feedback/stats", headers=_auth_only(ctx["headers"])
    )


@when("我送出認證 GET /api/v1/feedback/analysis/satisfaction-trend")
def get_satisfaction_trend(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/feedback/analysis/satisfaction-trend",
        headers=_auth_only(ctx["headers"]),
    )


@when("我不帶 token 送出 GET /api/v1/feedback")
def get_feedback_no_auth(ctx, client):
    ctx["response"] = client.get("/api/v1/feedback")


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then(parsers.parse('回應包含 rating 為 "{rating}"'))
def check_rating(ctx, rating):
    body = ctx["response"].json()
    assert body["rating"] == rating


@then(parsers.parse('回應包含 comment 為 "{comment}"'))
def check_comment(ctx, comment):
    body = ctx["response"].json()
    assert body["comment"] == comment


@then(parsers.parse("回應包含 {count:d} 筆回饋"))
def check_feedback_count(ctx, count):
    body = ctx["response"].json()
    assert len(body) == count


@then(parsers.parse("統計包含 total 為 {total:d}"))
def check_stats_total(ctx, total):
    body = ctx["response"].json()
    assert body["total"] == total


@then("回應為陣列")
def check_is_list(ctx):
    body = ctx["response"].json()
    assert isinstance(body, list)
