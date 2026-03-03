"""Conversation API Integration — BDD Step Definitions."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("integration/conversation/conversation_api.feature")


@pytest.fixture
def ctx():
    return {}


def _create_tenant_and_login(client, name: str) -> dict:
    resp = client.post("/api/v1/tenants", json={"name": name})
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]
    token_resp = client.post("/api/v1/auth/token", json={"tenant_id": tenant_id})
    assert token_resp.status_code == 200, token_resp.text
    token = token_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "_tenant_id": tenant_id}


def _auth_only(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('已登入為租戶 "{name}"'))
def login_as_tenant(ctx, client, name):
    ctx["headers"] = _create_tenant_and_login(client, name)


@given(parsers.parse('另一租戶 "{name}" 有對話記錄'))
def other_tenant_has_conversation(ctx, client, app, name):
    """Create a conversation for another tenant via direct DB insert."""
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    headers = _create_tenant_and_login(client, name)
    tenant_id = headers["_tenant_id"]

    async def _insert():
        eng = create_async_engine(
            "postgresql+asyncpg://postgres:postgres@localhost:5432/agentic_rag_test",
            poolclass=NullPool,
        )
        async with eng.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO conversations (id, tenant_id, created_at) "
                    "VALUES (gen_random_uuid(), :tid, now())"
                ),
                {"tid": tenant_id},
            )
        await eng.dispose()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_insert())
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("我送出認證 GET /api/v1/conversations")
def get_conversations(ctx, client):
    ctx["response"] = client.get(
        "/api/v1/conversations", headers=_auth_only(ctx["headers"])
    )


@when(
    parsers.parse("我送出認證 GET /api/v1/conversations/{conv_id}")
)
def get_conversation_by_id(ctx, client, conv_id):
    ctx["response"] = client.get(
        f"/api/v1/conversations/{conv_id}",
        headers=_auth_only(ctx["headers"]),
    )


@when("我不帶 token 送出 GET /api/v1/conversations")
def get_conversations_no_auth(ctx, client):
    ctx["response"] = client.get("/api/v1/conversations")


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then("回應為空陣列")
def check_empty_list(ctx):
    body = ctx["response"].json()
    assert isinstance(body, list)
    assert len(body) == 0
