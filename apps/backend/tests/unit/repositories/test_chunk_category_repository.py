"""SQLAlchemyChunkCategoryRepository — KB 範圍查詢、改名、刪除與指派（Issue #101）。

分類以 kb_id / category_id 操作；KB 歸屬由 ensure_kb_accessible 在呼叫端驗，
分類須再比對 cat.kb_id == 路徑 kb_id（見 tenant fence 理由）。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.knowledge.entity import ChunkCategory
from src.infrastructure.db.models.chunk_category_model import ChunkCategoryModel
from src.infrastructure.db.repositories.chunk_category_repository import (
    SQLAlchemyChunkCategoryRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> ChunkCategoryModel:
    data: dict = {
        "id": "cat-1",
        "kb_id": "kb-1",
        "tenant_id": "tenant-a",
        "name": "退換貨",
        "description": "d",
        "chunk_count": 4,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return ChunkCategoryModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyChunkCategoryRepository:
    return SQLAlchemyChunkCategoryRepository(session)  # type: ignore[arg-type]


def test_find_by_kb_scopes_kb_and_maps(session, repo):
    session.queue_result([_model()])
    (cat,) = _run(repo.find_by_kb("kb-1"))
    assert "chunk_categories.kb_id = 'kb-1'" in session.sql()
    assert (cat.kb_id, cat.tenant_id, cat.chunk_count) == ("kb-1", "tenant-a", 4)


def test_find_by_id(session, repo):
    session.queue_result([_model()])
    assert _run(repo.find_by_id("cat-1")).name == "退換貨"
    assert "chunk_categories.id = 'cat-1'" in session.sql()
    assert _run(repo.find_by_id("none")) is None


def test_save_and_save_batch_carry_tenant(session, repo):
    _run(repo.save(ChunkCategory(id="c1", kb_id="kb-1", tenant_id="tenant-a")))
    _run(
        repo.save_batch(
            [
                ChunkCategory(id="c2", kb_id="kb-1", tenant_id="tenant-a"),
                ChunkCategory(id="c3", kb_id="kb-1", tenant_id="tenant-a"),
            ]
        )
    )
    assert [m.id for m in session.added] == ["c1", "c2", "c3"]
    assert {m.tenant_id for m in session.added} == {"tenant-a"}
    assert session.commits == 2


def test_update_name_and_delete_by_kb(session, repo):
    _run(repo.update_name("cat-1", "新名"))
    sql = session.sql()
    assert "UPDATE chunk_categories" in sql and "chunk_categories.id = 'cat-1'" in sql
    assert "name='新名'" in sql.replace(" ", "")

    _run(repo.delete_by_kb("kb-1"))
    assert "DELETE FROM chunk_categories" in session.sql()
    assert "chunk_categories.kb_id = 'kb-1'" in session.sql()


def test_update_chunk_counts_resets_kb_then_sets_counts(session, repo):
    session.queue_result()  # reset UPDATE
    session.queue_result([("cat-1", 3), ("cat-2", 1)])
    _run(repo.update_chunk_counts("kb-1"))
    reset, count, upd1, upd2 = session.all_sql()
    assert "chunk_categories.kb_id = 'kb-1'" in reset
    assert "chunk_count=0" in reset.replace(" ", "")
    assert "count(*)" in count
    assert "chunk_categories.id = 'cat-1'" in upd1
    assert "chunk_count=3" in upd1.replace(" ", "")
    assert "chunk_categories.id = 'cat-2'" in upd2



def test_update_chunk_counts_only_counts_chunks_of_this_kb(session, repo):
    """Regression（#102）：計數子查詢原本統計全平台 chunk，每次分類都掃整張表。

    計數必須限定在該 KB 的分類，且逐筆更新也要綁 kb_id（不可能寫到別的 KB）。
    """
    session.queue_result()  # reset UPDATE
    session.queue_result([("cat-1", 3)])
    _run(repo.update_chunk_counts("kb-1"))
    _, count, upd = session.all_sql()
    assert "chunk_categories.kb_id = 'kb-1'" in count
    assert "chunk_categories.kb_id = 'kb-1'" in upd

def test_delete_by_id_unassigns_chunks_first(session, repo):
    _run(repo.delete_by_id("cat-1"))
    unassign, delete_ = session.all_sql()
    assert "UPDATE chunks" in unassign
    assert "chunks.category_id = 'cat-1'" in unassign
    assert "category_id=NULL" in unassign.replace(" ", "")
    assert "DELETE FROM chunk_categories" in delete_
    assert "chunk_categories.id = 'cat-1'" in delete_


def test_assign_chunks(session, repo):
    _run(repo.assign_chunks("cat-1", []))
    assert session.statements == []

    _run(repo.assign_chunks("cat-1", ["ch-1", "ch-2"]))
    sql = session.sql()
    assert "chunks.id IN ('ch-1', 'ch-2')" in sql
    assert "category_id='cat-1'" in sql.replace(" ", "")

    _run(repo.assign_chunks(None, ["ch-1"]))
    assert "category_id=NULL" in session.sql().replace(" ", "")
