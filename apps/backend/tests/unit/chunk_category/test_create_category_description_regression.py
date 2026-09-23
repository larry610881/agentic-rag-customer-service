"""Regression: 建立分類未給 description 時，回傳實體應為 "" 而非 None。

DB 欄位 `chunk_categories.description` 為 NOT NULL DEFAULT ''，ORM 會把 None
存成 ''；但 use case 原本把 None 直接塞進 ChunkCategory（型別宣告為 str），
導致 POST 回應 description=null、之後 GET 卻是 ""，同一筆資料前後不一致。
"""

from __future__ import annotations

from src.application.chunk_category.create_category_use_case import (
    CreateCategoryCommand,
    CreateCategoryUseCase,
)
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeCategoryRepo,
    FakeKbRepo,
    make_kb,
    run,
)


def test_missing_description_becomes_empty_string() -> None:
    kb_repo = FakeKbRepo()
    run(kb_repo.save(make_kb("kb-1", "T001")))
    cat_repo = FakeCategoryRepo()
    use_case = CreateCategoryUseCase(category_repo=cat_repo, kb_repo=kb_repo)

    cat = run(
        use_case.execute(
            CreateCategoryCommand(kb_id="kb-1", tenant_id="T001", name="飲料")
        )
    )

    assert cat.description == ""
    assert cat_repo.items[cat.id].description == ""
