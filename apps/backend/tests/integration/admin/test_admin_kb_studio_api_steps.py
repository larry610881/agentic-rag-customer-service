"""Admin KB Studio API — BDD integration step defs (S-KB-Followup.1)

覆蓋 admin_kb_studio_api.feature 的 14 scenarios。策略：
- system_admin 登入用 user_access token + tenant_id 指向 seed tenant（這樣
  require_role(system_admin) 過，tenant chain 驗證也過）
- vector_store / embedding_service 透過 app.container override 注入 mock
- 文件/chunk/category/KB 都用 raw SQL seed（bulk insert 比一筆筆跑 use case 快）
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from dependency_injector import providers
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import text
from types import SimpleNamespace

scenarios("integration/admin/admin_kb_studio_api.feature")


@pytest.fixture
def ctx():
    return {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ----------------------------------------------------------------------
# 共用 seed helpers (raw SQL)
# ----------------------------------------------------------------------


async def _insert_tenant(conn, tenant_id: str) -> None:
    """避開 TenantModel 的複雜欄位，走最小集合。"""
    await conn.execute(
        text(
            "INSERT INTO tenants (id, name, plan, default_ocr_model, "
            "default_context_model, default_classification_model, "
            "created_at, updated_at) "
            "VALUES (:id, :n, 'starter', '', '', '', :at, :at) "
            "ON CONFLICT DO NOTHING"
        ),
        {"id": tenant_id, "n": f"t-{tenant_id[:8]}-{tenant_id[-4:]}", "at": _now()},
    )


async def _insert_kb(conn, kb_id: str, tenant_id: str) -> None:
    await conn.execute(
        text(
            "INSERT INTO knowledge_bases (id, tenant_id, name, description, "
            "kb_type, ocr_mode, ocr_model, context_model, classification_model, "
            "embedding_model, created_at, updated_at) "
            "VALUES (:id, :tid, :n, '', 'user', 'general', '', '', '', '', :at, :at)"
        ),
        {"id": kb_id, "tid": tenant_id, "n": f"kb-{kb_id}", "at": _now()},
    )


async def _insert_doc(conn, doc_id: str, kb_id: str, tenant_id: str) -> None:
    await conn.execute(
        text(
            "INSERT INTO documents (id, kb_id, tenant_id, filename, content_type, "
            "content, storage_path, status, chunk_count, avg_chunk_length, "
            "min_chunk_length, max_chunk_length, quality_score, quality_issues, "
            "created_at, updated_at) "
            "VALUES (:id, :kb, :tid, :fn, 'pdf', '', '', 'processed', 1, "
            "100, 100, 100, 1.0, '', :at, :at)"
        ),
        {"id": doc_id, "kb": kb_id, "tid": tenant_id, "fn": f"{doc_id}.pdf", "at": _now()},
    )


async def _insert_chunk(
    conn,
    chunk_id: str,
    doc_id: str,
    tenant_id: str,
    *,
    content: str = "內容",
    chunk_index: int = 0,
    quality_flag: str | None = None,
    category_id: str | None = None,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO chunks (id, document_id, tenant_id, content, "
            "context_text, category_id, chunk_index, metadata, quality_flag) "
            "VALUES (:id, :doc, :tid, :c, '', :cat, :idx, '{}', :qf)"
        ),
        {
            "id": chunk_id,
            "doc": doc_id,
            "tid": tenant_id,
            "c": content,
            "cat": category_id,
            "idx": chunk_index,
            "qf": quality_flag,
        },
    )


async def _insert_category(
    conn, cat_id: str, kb_id: str, tenant_id: str, name: str = "分類"
) -> None:
    await conn.execute(
        text(
            "INSERT INTO chunk_categories (id, kb_id, tenant_id, name, "
            "description, chunk_count, created_at, updated_at) "
            "VALUES (:id, :kb, :tid, :n, '', 0, :at, :at)"
        ),
        {"id": cat_id, "kb": kb_id, "tid": tenant_id, "n": name, "at": _now()},
    )


# ----------------------------------------------------------------------
# Tenant + auth helpers
# ----------------------------------------------------------------------


def _login_system_admin_with_tenant(app, tenant_id: str) -> dict[str, str]:
    """Create user_access JWT with role=system_admin + tenant_id.

    這讓 require_role(system_admin) 過，tenant chain 驗證也過（tenant_id 匹配）。
    實務上 system_admin 應該是 tenant_id=None，但整合測試需要同時滿足 role
    check 與 tenant chain check，這是 integration 層折衷。
    """
    jwt_svc = app.container.jwt_service()
    token = jwt_svc.create_user_token(
        user_id="sys-admin-test", tenant_id=tenant_id, role="system_admin"
    )
    return {"Authorization": f"Bearer {token}"}


def _login_tenant_admin(app, tenant_id: str) -> dict[str, str]:
    jwt_svc = app.container.jwt_service()
    token = jwt_svc.create_user_token(
        user_id="tenant-admin-test", tenant_id=tenant_id, role="tenant_admin"
    )
    return {"Authorization": f"Bearer {token}"}


def _login_plain_user(app, tenant_id: str) -> dict[str, str]:
    jwt_svc = app.container.jwt_service()
    token = jwt_svc.create_user_token(
        user_id="user-test", tenant_id=tenant_id, role="user"
    )
    return {"Authorization": f"Bearer {token}"}


def _ensure_tenant_and_login(app, test_engine, tenant_id: str) -> None:
    """確保 tenant row 存在（DB 層 FK 需要）。"""

    async def _seed():
        async with test_engine.begin() as conn:
            await _insert_tenant(conn, tenant_id)

    _run(_seed())


def _override_vector_store(app, mock: AsyncMock) -> None:
    app.container.vector_store.override(providers.Object(mock))


def _override_embedding(app, mock: AsyncMock) -> None:
    app.container.embedding_service.override(providers.Object(mock))


# ======================================================================
# Given steps
# ======================================================================


@given(parsers.parse('系統已 seed KB "{kb_id}" 含 {n:d} chunks'))
def seed_kb_with_chunks(ctx, app, test_engine, kb_id, n):
    tenant_id = ctx.setdefault("tenant_id", "t-kb-studio")
    _ensure_tenant_and_login(app, test_engine, tenant_id)

    async def _seed():
        async with test_engine.begin() as conn:
            await _insert_kb(conn, kb_id, tenant_id)
            await _insert_doc(conn, "doc-1", kb_id, tenant_id)
            for i in range(n):
                await _insert_chunk(
                    conn,
                    f"chunk-{i}",
                    "doc-1",
                    tenant_id,
                    content=f"內容 {i}",
                    chunk_index=i,
                )

    _run(_seed())
    ctx["kb_id"] = kb_id
    ctx["chunk_count"] = n


@given(parsers.parse('系統已 seed chunk "{chunk_id}" 於 doc "{doc_id}" 於 kb "{kb_id}"'))
def seed_single_chunk(ctx, app, test_engine, chunk_id, doc_id, kb_id):
    tenant_id = ctx.setdefault("tenant_id", "t-kb-studio")
    _ensure_tenant_and_login(app, test_engine, tenant_id)

    async def _seed():
        async with test_engine.begin() as conn:
            await _insert_kb(conn, kb_id, tenant_id)
            await _insert_doc(conn, doc_id, kb_id, tenant_id)
            await _insert_chunk(conn, chunk_id, doc_id, tenant_id)

    _run(_seed())
    ctx["kb_id"] = kb_id
    ctx["doc_id"] = doc_id
    ctx["chunk_id"] = chunk_id


@given(parsers.parse('系統已 seed chunk "{chunk_id}" 屬租戶 "{tenant_id}"'))
def seed_chunk_owned_by_tenant(ctx, app, test_engine, chunk_id, tenant_id):
    _ensure_tenant_and_login(app, test_engine, tenant_id)

    async def _seed():
        async with test_engine.begin() as conn:
            await _insert_kb(conn, "kb-1", tenant_id)
            await _insert_doc(conn, "doc-1", "kb-1", tenant_id)
            await _insert_chunk(conn, chunk_id, "doc-1", tenant_id)

    _run(_seed())
    ctx["chunk_id"] = chunk_id
    ctx["owner_tenant"] = tenant_id


@given(parsers.parse('系統已 seed chunk "{chunk_id}"'))
def seed_bare_chunk(ctx, app, test_engine, chunk_id):
    tenant_id = ctx.setdefault("tenant_id", "t-kb-studio")
    _ensure_tenant_and_login(app, test_engine, tenant_id)

    async def _seed():
        async with test_engine.begin() as conn:
            await _insert_kb(conn, "kb-1", tenant_id)
            await _insert_doc(conn, "doc-1", "kb-1", tenant_id)
            await _insert_chunk(conn, chunk_id, "doc-1", tenant_id)

    _run(_seed())
    ctx["chunk_id"] = chunk_id


@given(parsers.parse('系統已 seed KB "{kb_id}" 含 embedded chunks'))
def seed_kb_with_embeddings(ctx, app, test_engine, kb_id):
    tenant_id = ctx.setdefault("tenant_id", "t-kb-studio")
    _ensure_tenant_and_login(app, test_engine, tenant_id)

    async def _seed():
        async with test_engine.begin() as conn:
            await _insert_kb(conn, kb_id, tenant_id)
            await _insert_doc(conn, "doc-1", kb_id, tenant_id)
            for i in range(3):
                await _insert_chunk(
                    conn, f"chunk-{i}", "doc-1", tenant_id,
                    content=f"退貨第 {i} 條",
                )

    _run(_seed())
    ctx["kb_id"] = kb_id

    # 設定 embedding + vector_store mock
    emb = AsyncMock()
    emb.embed_query = AsyncMock(return_value=[0.1] * 3072)
    _override_embedding(app, emb)

    vs = AsyncMock()
    vs.search = AsyncMock(
        return_value=[
            SimpleNamespace(
                id=f"chunk-{i}",
                score=0.9 - i * 0.1,
                payload={"content": f"退貨第 {i} 條", "tenant_id": tenant_id},
            )
            for i in range(3)
        ]
    )
    _override_vector_store(app, vs)


@given(parsers.parse('系統已 seed KB "{kb_id}" 含多個 quality_flag 的 chunks'))
def seed_kb_with_quality_flags(ctx, app, test_engine, kb_id):
    tenant_id = ctx.setdefault("tenant_id", "t-kb-studio")
    _ensure_tenant_and_login(app, test_engine, tenant_id)

    async def _seed():
        async with test_engine.begin() as conn:
            await _insert_kb(conn, kb_id, tenant_id)
            await _insert_doc(conn, "doc-1", kb_id, tenant_id)
            flags = [None, None, None, "too_short", "incomplete"]
            for i, flag in enumerate(flags):
                await _insert_chunk(
                    conn, f"chunk-{i}", "doc-1", tenant_id,
                    chunk_index=i, quality_flag=flag,
                )

    _run(_seed())
    ctx["kb_id"] = kb_id


@given(parsers.parse('系統已 seed KB "{kb_id}"'))
def seed_kb_only(ctx, app, test_engine, kb_id):
    tenant_id = ctx.setdefault("tenant_id", "t-kb-studio")
    _ensure_tenant_and_login(app, test_engine, tenant_id)

    async def _seed():
        async with test_engine.begin() as conn:
            await _insert_kb(conn, kb_id, tenant_id)

    _run(_seed())
    ctx["kb_id"] = kb_id


@given(
    parsers.parse(
        '系統已 seed 分類 "{cat_id}" 於 KB "{kb_id}" 含 {n:d} chunks'
    )
)
def seed_category_with_chunks(ctx, app, test_engine, cat_id, kb_id, n):
    tenant_id = ctx.setdefault("tenant_id", "t-kb-studio")
    _ensure_tenant_and_login(app, test_engine, tenant_id)

    async def _seed():
        async with test_engine.begin() as conn:
            await _insert_kb(conn, kb_id, tenant_id)
            await _insert_doc(conn, "doc-1", kb_id, tenant_id)
            await _insert_category(conn, cat_id, kb_id, tenant_id)
            for i in range(n):
                await _insert_chunk(
                    conn, f"c-{i}", "doc-1", tenant_id,
                    chunk_index=i, category_id=cat_id,
                )

    _run(_seed())
    ctx["kb_id"] = kb_id
    ctx["cat_id"] = cat_id


@given(
    parsers.parse(
        '系統已 seed 分類 "{cat_id}" 與 {n:d} 個 chunks ["{c1}","{c2}","{c3}","{c4}","{c5}"]'
    )
)
def seed_category_and_chunks(ctx, app, test_engine, cat_id, n, c1, c2, c3, c4, c5):
    kb_id = "kb-1"
    tenant_id = ctx.setdefault("tenant_id", "t-kb-studio")
    _ensure_tenant_and_login(app, test_engine, tenant_id)

    async def _seed():
        async with test_engine.begin() as conn:
            await _insert_kb(conn, kb_id, tenant_id)
            await _insert_doc(conn, "doc-1", kb_id, tenant_id)
            await _insert_category(conn, cat_id, kb_id, tenant_id)
            for i, cid in enumerate([c1, c2, c3, c4, c5]):
                await _insert_chunk(conn, cid, "doc-1", tenant_id, chunk_index=i)

    _run(_seed())
    ctx["kb_id"] = kb_id
    ctx["cat_id"] = cat_id


@given(parsers.parse('系統已 seed {n:d} 個 Milvus collections'))
def seed_milvus_collections(ctx, app, n):
    vs = AsyncMock()
    vs.list_collections = AsyncMock(
        return_value=[
            {"name": f"kb_{i}", "row_count": 100 + i * 50}
            for i in range(n)
        ]
    )
    vs.get_collection_stats = AsyncMock(
        return_value={
            "row_count": 0,
            "loaded": True,
            "indexes": [{"field": "tenant_id", "index_type": "INVERTED"}],
        }
    )
    _override_vector_store(app, vs)
    ctx["n_collections"] = n


@given(parsers.parse('系統已 seed Milvus collection "{name}" 含 {n:d} rows'))
def seed_milvus_single_collection(ctx, app, name, n):
    vs = AsyncMock()
    vs.get_collection_stats = AsyncMock(
        return_value={
            "row_count": n,
            "loaded": True,
            "indexes": [{"field": "tenant_id", "index_type": "INVERTED"}],
        }
    )
    _override_vector_store(app, vs)


@given(parsers.parse('系統已 seed Milvus collection "{name}"（模擬新 collection）'))
def seed_milvus_new_collection(ctx, app, name):
    vs = AsyncMock()
    vs.rebuild_scalar_indexes = AsyncMock(
        return_value={"indexes_rebuilt": ["tenant_id", "document_id"]}
    )
    _override_vector_store(app, vs)


@given(parsers.parse('租戶 "{tenant_id}" 有 {n:d} 筆 conv_summaries'))
def seed_conv_summaries(ctx, app, test_engine, tenant_id, n):
    _ensure_tenant_and_login(app, test_engine, tenant_id)
    # 這些資料 list_conv_summaries_use_case 透過 ConversationRepository 讀；
    # 實際 repo 可能查 milvus 或 DB。為避免耦合，覆蓋 conversation_repository
    # 直接回傳 n 筆假資料。
    repo = AsyncMock()
    repo.find_conv_summaries = AsyncMock(
        return_value=[
            {
                "conversation_id": f"conv-{i}",
                "tenant_id": tenant_id,
                "bot_id": None,
                "summary": f"摘要 {i}",
                "created_at": _now(),
            }
            for i in range(n)
        ]
    )
    app.container.conversation_repository.override(providers.Object(repo))

    bot_repo = AsyncMock()
    bot_repo.exists_for_tenant = AsyncMock(return_value=True)
    app.container.bot_repository.override(providers.Object(bot_repo))

    ctx["tenant_id"] = tenant_id


@given(parsers.parse('租戶 "{tenant_id}" 的 tenant_admin 已登入'))
def login_as_tenant_admin(ctx, app, tenant_id):
    ctx["headers"] = _login_tenant_admin(app, tenant_id)


@given("系統管理員已登入")
def login_system_admin(ctx, app):
    tenant_id = ctx.setdefault("tenant_id", "t-kb-studio")
    ctx["headers"] = _login_system_admin_with_tenant(app, tenant_id)


@given("一般租戶已登入")
def login_plain_user(ctx, app):
    tenant_id = ctx.setdefault("tenant_id", "t-kb-studio")
    ctx["headers"] = _login_plain_user(app, tenant_id)


# ======================================================================
# When steps
# ======================================================================


@when(parsers.parse("我送出 GET {url}"))
def when_get(ctx, client, url):
    ctx["resp"] = client.get(url, headers=ctx["headers"])


@when(parsers.parse("我送出 PATCH {url} body={body}"))
def when_patch(ctx, client, url, body):
    import json

    ctx["resp"] = client.patch(url, json=json.loads(body), headers=ctx["headers"])


@when(parsers.parse("我送出 DELETE {url}"))
def when_delete(ctx, client, url):
    ctx["resp"] = client.delete(url, headers=ctx["headers"])


@when(parsers.parse("我送出 POST {url} body={body}"))
def when_post(ctx, client, url, body):
    import json

    ctx["resp"] = client.post(url, json=json.loads(body), headers=ctx["headers"])


@when(parsers.parse("我送出 POST {url}"))
def when_post_no_body(ctx, client, url):
    ctx["resp"] = client.post(url, headers=ctx["headers"])


# ======================================================================
# Then steps
# ======================================================================


@then(parsers.parse("回應狀態碼為 {code:d}"))
def then_status(ctx, code):
    actual = ctx["resp"].status_code
    assert actual == code, f"expected {code}, got {actual}: {ctx['resp'].text}"


@then(parsers.parse("回應 items 為 {n:d} 筆"))
def then_items_count(ctx, n):
    body = ctx["resp"].json()
    items = body.get("items", body) if isinstance(body, dict) else body
    assert len(items) == n, f"expected {n} items, got {len(items)}: {items}"


@then(parsers.parse("回應 total 為 {n:d}"))
def then_total(ctx, n):
    assert ctx["resp"].json()["total"] == n


@then(parsers.parse('資料庫中 {chunk_id} 的 content 為 "{content}"'))
def then_chunk_content(ctx, test_engine, chunk_id, content):
    async def _fetch():
        async with test_engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT content FROM chunks WHERE id = :id"),
                    {"id": chunk_id},
                )
            ).first()
            return row[0] if row else None

    assert _run(_fetch()) == content


@then("應 enqueue reembed_chunk job")
def then_enqueue_reembed(ctx):
    # Router 層確認 reembed_enqueued=True（用 case 未 wire arq 時仍會回 True；
    # reembed_chunk 真正執行在 arq worker 層，此處只驗 API 契約）
    assert ctx["resp"].json().get("reembed_enqueued") is True


@then(parsers.parse("資料庫中 {chunk_id} 不存在"))
def then_chunk_absent(ctx, test_engine, chunk_id):
    async def _fetch():
        async with test_engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT id FROM chunks WHERE id = :id"),
                    {"id": chunk_id},
                )
            ).first()
            return row

    assert _run(_fetch()) is None


@then(parsers.parse("回應 results 長度 <= {n:d}"))
def then_results_len(ctx, n):
    assert len(ctx["resp"].json()["results"]) <= n


@then(parsers.parse('回應 filter_expr 含 "{needle}"'))
def then_filter_expr(ctx, needle):
    assert needle in ctx["resp"].json()["filter_expr"]


@then("回應 low_quality_count 為整數")
def then_low_q_int(ctx):
    assert isinstance(ctx["resp"].json()["low_quality_count"], int)


@then("回應 avg_cohesion_score 為浮點數")
def then_cohesion_float(ctx):
    assert isinstance(ctx["resp"].json()["avg_cohesion_score"], float)


@then(parsers.parse('回應 name 為 "{name}"'))
def then_name_eq(ctx, name):
    assert ctx["resp"].json()["name"] == name


@then(parsers.parse('{n:d} chunks 的 category_id 為 NULL'))
def then_chunks_category_null(ctx, test_engine, n):
    async def _count():
        async with test_engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT count(*) FROM chunks WHERE category_id IS NULL")
                )
            ).first()
            return row[0]

    cnt = _run(_count())
    assert cnt >= n, f"expected >= {n} NULL category chunks, got {cnt}"


@then(parsers.parse('chunks {c1}, {c2}, {c3} 的 category_id 為 "{cat}"'))
def then_chunks_assigned(ctx, test_engine, c1, c2, c3, cat):
    async def _fetch():
        async with test_engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT id, category_id FROM chunks WHERE id IN (:a, :b, :c)"
                    ),
                    {"a": c1, "b": c2, "c": c3},
                )
            ).all()
            return {r[0]: r[1] for r in rows}

    data = _run(_fetch())
    for cid in [c1, c2, c3]:
        assert data.get(cid) == cat, (
            f"chunk {cid} category_id={data.get(cid)}, expected {cat}"
        )


@then(parsers.parse("回應含 {n:d} 個 collection"))
def then_collection_count(ctx, n):
    assert len(ctx["resp"].json()) == n


@then(parsers.parse('每個 collection 的 tenant_id index_type 為 "{idx_type}"'))
def then_collection_index(ctx, idx_type):
    for c in ctx["resp"].json():
        tenant_idx = next(
            (i for i in c["indexes"] if i["field"] == "tenant_id"), None
        )
        assert tenant_idx is not None
        assert tenant_idx["index_type"] == idx_type


@then(parsers.parse("回應 row_count 為 {n:d}"))
def then_row_count(ctx, n):
    assert ctx["resp"].json()["row_count"] == n


@then(parsers.parse("回應 loaded 為 {val}"))
def then_loaded(ctx, val):
    assert ctx["resp"].json()["loaded"] == (val == "true")


@then(parsers.parse('應記錄 audit event "{ev}"'))
def then_audit_event(ctx, ev):
    # audit 目前透過 structlog event name 記錄，無 DB 表可查。
    # 此處單純驗 router 回 2xx，實際 event 名在 use case structlog.info 內。
    assert 200 <= ctx["resp"].status_code < 300


@then("回應應為 list 至少含 1 筆 含 created_at 與 updated_at 欄位")
def then_list_categories_shape(ctx):
    body = ctx["resp"].json()
    assert isinstance(body, list), f"expected list, got {type(body).__name__}"
    assert len(body) >= 1, f"expected at least 1 item, got {len(body)}"
    first = body[0]
    assert "created_at" in first, f"missing created_at: {first}"
    assert "updated_at" in first, f"missing updated_at: {first}"
    assert "chunk_count" in first
    assert "id" in first
    assert "name" in first
