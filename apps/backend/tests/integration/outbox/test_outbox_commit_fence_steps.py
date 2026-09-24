"""Outbox 提交圍欄 — BDD Step Definitions（#469966）。

圍欄判定：request 結束後，從 **全新連線**（NullPool engine 的新 TCP 連線）查
``outbox_events``；看得到 = 已 commit。

證明圍欄會紅：第二個 scenario 在測試 app 上掛一個只存在於測試的端點，它在真實
HTTP request 內透過 container 解析 ``PublishOutboxEventUseCase`` 並只呼叫
``execute(event)``（無 atomic 寫入、無 commit），再用同一個 request session 回報
事件「在 request 內看得到」— 所以事件確實寫過，只是沒提交；圍欄必須判定為未提交。
第三個 scenario 用同一端點改走 ``standalone=True``（repository 自行 commit）當正向
對照，證明兩者差別只在 commit。不修改任何 production 程式碼。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import text

from src.domain.outbox.events import vector_delete_event
from tests.integration.conftest import TEST_DB_NAME, _run

scenarios("integration/outbox/outbox_commit_fence.feature")

_TEST_ROUTE = "/__test__/outbox-publish-only"


@pytest.fixture
def ctx():
    return {}


def _auth(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if not k.startswith("_")}


def _committed_outbox_event_types(engine, aggregate_id: str) -> list[str]:
    """圍欄本體：全新連線只看得到已 commit 的 row。"""

    async def _q():
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT event_type FROM outbox_events "
                    "WHERE aggregate_id = :aid"
                ),
                {"aid": aggregate_id},
            )
            return [r[0] for r in rows]

    return _run(_q())


def _idle_in_transaction_count(engine) -> int:
    async def _q():
        async with engine.connect() as conn:
            row = await conn.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = :db AND state = 'idle in transaction' "
                    "AND pid <> pg_backend_pid()"
                ),
                {"db": TEST_DB_NAME},
            )
            return row.scalar_one()

    return _run(_q())


def _mount_publish_only_route(app, ctx, *, standalone: bool) -> None:
    """測試專用端點：在真實 request 內 publish，並回報 request session 內可見數。"""
    aggregate_id = str(uuid4())
    ctx["aggregate_id"] = aggregate_id
    container = app.container

    async def _publish_only() -> dict:
        event = vector_delete_event(
            tenant_id=str(uuid4()),
            aggregate_type="document",
            aggregate_id=aggregate_id,
            collection="kb_fence",
            filters={"document_id": [aggregate_id]},
        )
        await container.publish_outbox_event_use_case().execute(
            event, standalone=standalone
        )
        # 同一個 per-request session（get_tracked_session）：flush 把 INSERT 送進
        # 本 transaction（仍未 commit），證明事件確實寫到了 request 的 session。
        # 若拿到的是別的 session，flush 不含這筆 row，count 會是 0。
        session = container.db_session()
        await session.flush()
        visible = await session.execute(
            text("SELECT count(*) FROM outbox_events WHERE aggregate_id = :aid"),
            {"aid": aggregate_id},
        )
        return {"visible_in_request": visible.scalar_one()}

    app.add_api_route(_TEST_ROUTE, _publish_only, methods=["POST"])


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(parsers.parse('已登入為租戶 "{name}" 並建立知識庫 "{kb_name}"'))
def setup_tenant_and_kb(ctx, client, create_tenant_login, name, kb_name):
    ctx["headers"] = create_tenant_login(name)
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={"name": kb_name},
        headers=_auth(ctx["headers"]),
    )
    assert resp.status_code == 201, resp.text
    ctx["kb_id"] = resp.json()["id"]


@given("該知識庫已有一份文件")
def upload_document(ctx, client):
    resp = client.post(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents",
        files={"file": ("fence.txt", b"fence body", "text/plain")},
        headers=_auth(ctx["headers"]),
    )
    assert resp.status_code == 201, resp.text
    ctx["aggregate_id"] = resp.json()["document"]["id"]


@given("測試用端點只 publish outbox 事件而沒有任何 atomic 寫入")
def mount_publish_only(ctx, app):
    _mount_publish_only_route(app, ctx, standalone=False)


@given("測試用端點以 standalone 模式 publish outbox 事件")
def mount_publish_standalone(ctx, app):
    _mount_publish_only_route(app, ctx, standalone=True)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when("我透過 HTTP 刪除該文件")
def delete_document(ctx, client):
    ctx["response"] = client.delete(
        f"/api/v1/knowledge-bases/{ctx['kb_id']}/documents/{ctx['aggregate_id']}",
        headers=_auth(ctx["headers"]),
    )


@when("我呼叫該測試用端點")
def call_test_route(ctx, client):
    ctx["response"] = client.post(_TEST_ROUTE)


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("回應狀態碼為 {code:d}"))
def then_status(ctx, code):
    assert ctx["response"].status_code == code, ctx["response"].text


@then("全新連線應看得到該文件的 vector.delete outbox 事件")
def then_delete_event_committed(ctx, test_engine):
    types = _committed_outbox_event_types(test_engine, ctx["aggregate_id"])
    assert types == ["vector.delete"], (
        f"DELETE 回 204 但 outbox 事件未提交（全新連線看到 {types}）"
    )


@then("request 內的 session 看得到該事件")
def then_visible_in_request(ctx):
    assert ctx["response"].json() == {"visible_in_request": 1}


@then("全新連線不應看得到該事件")
def then_not_committed(ctx, test_engine):
    types = _committed_outbox_event_types(test_engine, ctx["aggregate_id"])
    assert types == [], f"未 commit 的事件卻被全新連線看到：{types}"


@then("全新連線應看得到該事件")
def then_committed(ctx, test_engine):
    types = _committed_outbox_event_types(test_engine, ctx["aggregate_id"])
    assert types == ["vector.delete"], f"standalone publish 未提交：{types}"


@then("request 結束後測試資料庫不應殘留 idle in transaction 連線")
def then_no_idle_in_transaction(test_engine):
    assert _idle_in_transaction_count(test_engine) == 0
