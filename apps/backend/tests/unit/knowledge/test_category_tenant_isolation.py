"""Regression：分類端點缺知識庫擁有權檢查（跨租戶資料隔離，Issue #100 B4 發現）。

建立 / 刪除 / 指派三個分類端點都走 ensure_kb_accessible，但以下四個漏了：
- GET   /knowledge-bases/{kb_id}/categories                 列出別家租戶的分類
- PATCH /knowledge-bases/{kb_id}/categories/{cat_id}        改別家租戶的分類名
- GET   /knowledge-bases/{kb_id}/categories/{cat_id}/chunks 讀別家租戶的文件內容
- POST  /knowledge-bases/{kb_id}/classify                   觸發別家租戶 KB 的分類工作
跨租戶一律 404（防枚舉），且不得讀寫資料。
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.knowledge.entity import ChunkCategory, KnowledgeBase
from src.domain.knowledge.value_objects import KnowledgeBaseId
from src.interfaces.api import knowledge_base_router as r
from src.interfaces.api.deps import CurrentTenant

ATTACKER = CurrentTenant(tenant_id="tenant-a", user_id="u-a")


def _kb_repo_owned_by_b() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_id.return_value = KnowledgeBase(
        id=KnowledgeBaseId(value="kb-b"), tenant_id="tenant-b", name="B 的知識庫"
    )
    return repo


def _cat_repo_of_b() -> AsyncMock:
    repo = AsyncMock()
    cat = ChunkCategory(id="cat-b", kb_id="kb-b", tenant_id="tenant-b", name="機密")
    repo.find_by_id.return_value = cat
    repo.find_by_kb.return_value = [cat]
    return repo


def test_跨租戶不能列出分類():
    cat_repo = _cat_repo_of_b()
    with pytest.raises(r.ApiError):
        asyncio.run(
            r.list_categories(
                kb_id="kb-b",
                tenant=ATTACKER,
                cat_repo=cat_repo,
                kb_repo=_kb_repo_owned_by_b(),
            )
        )
    cat_repo.find_by_kb.assert_not_awaited()


def test_跨租戶不能改分類名():
    cat_repo = _cat_repo_of_b()
    with pytest.raises(r.ApiError):
        asyncio.run(
            r.update_category(
                kb_id="kb-b",
                cat_id="cat-b",
                body=r.UpdateCategoryRequest(name="被竄改"),
                tenant=ATTACKER,
                cat_repo=cat_repo,
                kb_repo=_kb_repo_owned_by_b(),
            )
        )
    cat_repo.update_name.assert_not_awaited()


def test_跨租戶不能讀分類內的_chunk():
    use_case = AsyncMock()
    with pytest.raises(r.ApiError):
        asyncio.run(
            r.get_category_chunks(
                kb_id="kb-b",
                cat_id="cat-b",
                tenant=ATTACKER,
                use_case=use_case,
                kb_repo=_kb_repo_owned_by_b(),
            )
        )
    use_case.execute.assert_not_awaited()


def test_跨租戶不能觸發分類工作():
    with patch(
        "src.infrastructure.queue.arq_pool.enqueue", new=AsyncMock()
    ) as enqueue, pytest.raises(r.ApiError):
        asyncio.run(
            r.classify_knowledge_base(
                kb_id="kb-b", tenant=ATTACKER, kb_repo=_kb_repo_owned_by_b()
            )
        )
    enqueue.assert_not_awaited()


def test_同一分類若不屬於路徑上的_KB_也要拒絕():
    """同租戶但 cat_id 屬於另一個 KB：不能拿 A 知識庫的路徑改 B 知識庫的分類。"""
    kb_repo = AsyncMock()
    kb_repo.find_by_id.return_value = KnowledgeBase(
        id=KnowledgeBaseId(value="kb-a"), tenant_id="tenant-a", name="A"
    )
    cat_repo = AsyncMock()
    cat_repo.find_by_id.return_value = ChunkCategory(
        id="cat-x", kb_id="kb-other", tenant_id="tenant-a", name="x"
    )
    with pytest.raises(r.ApiError):
        asyncio.run(
            r.update_category(
                kb_id="kb-a",
                cat_id="cat-x",
                body=r.UpdateCategoryRequest(name="y"),
                tenant=ATTACKER,
                cat_repo=cat_repo,
                kb_repo=kb_repo,
            )
        )
    cat_repo.update_name.assert_not_awaited()
