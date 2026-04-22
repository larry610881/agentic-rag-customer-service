"""BDD: unit/milvus/list_collections.feature"""

from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.milvus.get_collection_stats_use_case import (
    GetCollectionStatsQuery,
    GetCollectionStatsUseCase,
)
from src.application.milvus.list_collections_use_case import (
    ListCollectionsQuery,
    ListCollectionsUseCase,
)
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeKbRepo,
    FakeVectorStore,
    make_kb,
    run,
)

scenarios("unit/milvus/list_collections.feature")


@pytest.fixture
def ctx():
    return {}


@given(parsers.parse('Milvus 有 collections: "{c1}"({r1:d} rows), "{c2}"({r2:d} rows), "{c3}"({r3:d} rows)'))
def seed_three(ctx, c1, r1, c2, r2, c3, r3):
    vs = FakeVectorStore()
    vs.collections_info = [
        {"name": c1, "row_count": r1},
        {"name": c2, "row_count": r2},
        {"name": c3, "row_count": r3},
    ]
    for name in (c1, c2, c3):
        vs.stats_by_col[name] = {
            "row_count": 0,  # filled from collections_info
            "loaded": True,
            "indexes": [
                {"field": "tenant_id", "index_type": "INVERTED"},
                {"field": "document_id", "index_type": "INVERTED"},
                {"field": "vector", "index_type": "AUTOINDEX"},
            ],
        }
    ctx.update(vs=vs, kb_repo=FakeKbRepo())


@given(parsers.parse('租戶 "{t1}" 擁有 2 KBs "{k1}" 與 "{k2}"'))
def seed_t1_two(ctx, t1, k1, k2):
    kb_repo = FakeKbRepo()
    run(kb_repo.save(make_kb(k1, t1)))
    run(kb_repo.save(make_kb(k2, t1)))
    vs = FakeVectorStore()
    vs.collections_info = [
        {"name": f"kb_{k1}", "row_count": 100},
        {"name": f"kb_{k2}", "row_count": 50},
        {"name": "conv_summaries", "row_count": 33},
    ]
    ctx.update(vs=vs, kb_repo=kb_repo)


@given(parsers.parse('租戶 "{t2}" 擁有 1 KB "{k3}"'))
def seed_t2(ctx, t2, k3):
    run(ctx["kb_repo"].save(make_kb(k3, t2)))
    ctx["vs"].collections_info.append(
        {"name": f"kb_{k3}", "row_count": 25}
    )


@given(parsers.parse('Milvus collection "{name}" 有 {n:d} rows'))
def seed_single(ctx, name, n):
    vs = ctx.get("vs") or FakeVectorStore()
    vs.stats_by_col[name] = {
        "row_count": n,
        "loaded": True,
        "indexes": [
            {"field": "tenant_id", "index_type": "INVERTED"},
            {"field": "document_id", "index_type": "INVERTED"},
            {"field": "vector", "index_type": "AUTOINDEX"},
        ],
    }
    ctx["vs"] = vs


@when("我以 platform_admin 身分呼叫 list_collections()")
def when_platform(ctx):
    uc = ListCollectionsUseCase(ctx["vs"], ctx["kb_repo"])
    ctx["result"] = run(
        uc.execute(ListCollectionsQuery(role="system_admin", tenant_id=None))
    )


@when(parsers.parse('我以 tenant "{tenant}" 的 tenant_admin 身分呼叫 list_collections()'))
def when_tenant(ctx, tenant):
    uc = ListCollectionsUseCase(ctx["vs"], ctx["kb_repo"])
    ctx["result"] = run(
        uc.execute(ListCollectionsQuery(role="tenant_admin", tenant_id=tenant))
    )


@when(parsers.parse('我以 platform_admin 身分呼叫 get_collection_stats("{name}")'))
def when_stats(ctx, name):
    uc = GetCollectionStatsUseCase(ctx["vs"])
    ctx["stats"] = run(uc.execute(GetCollectionStatsQuery(collection_name=name)))


@then(parsers.parse("回傳應含 {n:d} 個 collection"))
def then_count(ctx, n):
    assert len(ctx["result"]) == n


@then(parsers.parse('{name} 的 tenant_id index_type 應為 "{t}"（已 hotfix）'))
def then_idx_hotfix(ctx, name, t):
    col = next(c for c in ctx["result"] if c.name == name)
    tid_idx = next(i for i in col.indexes if i["field"] == "tenant_id")
    assert tid_idx["index_type"] == t


@then(parsers.parse('{name} 的 tenant_id index_type 應為 "{t}"'))
def then_idx_simple(ctx, name, t):
    col = next(c for c in ctx["result"] if c.name == name)
    tid_idx = next(i for i in col.indexes if i["field"] == "tenant_id")
    assert tid_idx["index_type"] == t


@then(parsers.parse('回傳應含 "{c1}" 與 "{c2}"'))
def then_has_two(ctx, c1, c2):
    names = {c.name for c in ctx["result"]}
    assert c1 in names and c2 in names


@then(parsers.parse('回傳不應含 "{name}"（跨租戶）'))
def then_not_cross(ctx, name):
    assert name not in {c.name for c in ctx["result"]}


@then(parsers.parse('回傳不應含 "{name}"（platform 專屬）'))
def then_not_platform(ctx, name):
    assert name not in {c.name for c in ctx["result"]}


@then(parsers.parse("回傳 row_count 應為 {n:d}"))
def then_stats_rows(ctx, n):
    assert ctx["stats"]["row_count"] == n


@then("回傳 loaded 應為 True")
def then_stats_loaded(ctx):
    assert ctx["stats"]["loaded"] is True


@then(parsers.parse('回傳 indexes 應含 {{"field": "{field}", "index_type": "{t}"}}'))
def then_stats_idx(ctx, field, t):
    assert any(
        i["field"] == field and i["index_type"] == t
        for i in ctx["stats"]["indexes"]
    )
