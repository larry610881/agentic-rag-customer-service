"""E2E Journey: 回饋分析流程"""

import asyncio
import uuid

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

scenarios("e2e/feedback_analysis.feature")

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/agentic_rag_e2e"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {}


def _auth(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


@given("已完成租戶設定並有對話記錄")
def setup_tenant_and_conversation(ctx, client):
    # Create tenant + token
    resp = client.post("/api/v1/tenants", json={"name": "feedback-e2e"})
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    token_resp = client.post("/api/v1/auth/token", json={"tenant_id": tenant_id})
    token = token_resp.json()["access_token"]
    ctx["headers"] = {"Authorization": f"Bearer {token}", "_tenant_id": tenant_id}

    # Insert conversation + 2 messages directly
    conv_id = str(uuid.uuid4())
    msg_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    ctx["conversation_id"] = conv_id
    ctx["message_ids"] = msg_ids

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
            for mid in msg_ids:
                await conn.execute(
                    text(
                        "INSERT INTO messages "
                        "(id, conversation_id, role, content, "
                        "tool_calls_json, created_at) "
                        "VALUES (:mid, :cid, 'assistant', 'AI 回覆', "
                        "'[]', now())"
                    ),
                    {"mid": mid, "cid": conv_id},
                )
        await eng.dispose()

    _run(_insert())


@when(parsers.parse('我提交回饋 評分 "{rating}" 到第 {n:d} 則訊息'))
def submit_feedback(ctx, client, rating, n):
    ctx["response"] = client.post(
        "/api/v1/feedback",
        json={
            "conversation_id": ctx["conversation_id"],
            "message_id": ctx["message_ids"][n - 1],
            "rating": rating,
        },
        headers=_auth(ctx["headers"]),
    )


@when(
    parsers.parse(
        '我提交回饋 評分 "{rating}" 留言 "{comment}" 到第 {n:d} 則訊息'
    )
)
def submit_feedback_with_comment(ctx, client, rating, comment, n):
    ctx["response"] = client.post(
        "/api/v1/feedback",
        json={
            "conversation_id": ctx["conversation_id"],
            "message_id": ctx["message_ids"][n - 1],
            "rating": rating,
            "comment": comment,
        },
        headers=_auth(ctx["headers"]),
    )


@when("我查詢回饋統計")
def get_stats(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/feedback/stats",
        headers=_auth(ctx["headers"]),
    )


@when("我查詢回饋列表")
def get_list(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/feedback",
        headers=_auth(ctx["headers"]),
    )


@when("我查詢滿意度趨勢")
def get_trend(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/feedback/analysis/satisfaction-trend",
        headers=_auth(ctx["headers"]),
    )


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then(parsers.parse("統計 total 為 {n:d}"))
def check_total(ctx, n):
    assert ctx["response"].json()["total"] == n


@then(parsers.parse("統計 thumbs_up 為 {n:d}"))
def check_thumbs_up(ctx, n):
    assert ctx["response"].json()["thumbs_up"] == n


@then(parsers.parse("回饋列表包含 {n:d} 筆"))
def check_feedback_count(ctx, n):
    assert len(ctx["response"].json()) == n


@then("回應為陣列格式")
def check_is_list(ctx):
    assert isinstance(ctx["response"].json(), list)
