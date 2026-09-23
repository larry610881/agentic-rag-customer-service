"""Regression：更新分類名稱後重新讀取時分類已被刪除（並行刪除）。

修正前：第二次 find_by_id 回傳 None，直接存取 cat.id → AttributeError → 500。
修正後：回 404 category_not_found，與「一開始就找不到」一致。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.domain.knowledge.entity import ChunkCategory, KnowledgeBase
from src.domain.knowledge.repository import ChunkCategoryRepository
from src.domain.knowledge.value_objects import KnowledgeBaseId
from src.interfaces.api.deps import CurrentTenant
from src.interfaces.api.errors import ApiError
from src.interfaces.api.knowledge_base_router import (
    UpdateCategoryRequest,
    update_category,
)


def test_category_deleted_between_rename_and_refetch_returns_404():
    repo = AsyncMock(spec=ChunkCategoryRepository)
    repo.find_by_id.side_effect = [
        ChunkCategory(id="cat-1", kb_id="kb-1", name="舊名"),
        None,
    ]

    kb_repo = AsyncMock()
    kb_repo.find_by_id.return_value = KnowledgeBase(
        id=KnowledgeBaseId(value="kb-1"), tenant_id="t1", name="kb"
    )

    with pytest.raises(ApiError) as exc_info:
        asyncio.run(
            update_category(
                kb_id="kb-1",
                cat_id="cat-1",
                body=UpdateCategoryRequest(name="新名"),
                tenant=CurrentTenant(tenant_id="t1"),
                cat_repo=repo,
                kb_repo=kb_repo,
            )
        )

    assert exc_info.value.status_code == 404
    repo.update_name.assert_awaited_once_with("cat-1", "新名")
