"""Regression test: system_admin bypass tenant check in ListKbChunksUseCase.

對應 bug：admin (tenant_id=SYSTEM_TENANT_ID) 進 KB Studio 看其他租戶的 KB chunks
之前嚴格 tenant 檢查 → 404 not found
修法：query.tenant_id == SYSTEM_TENANT_ID 時 bypass kb.tenant_id 比對
"""

from __future__ import annotations

import asyncio

import pytest

from src.application.knowledge.list_kb_chunks_use_case import (
    ListKbChunksQuery,
    ListKbChunksUseCase,
)
from src.domain.shared.constants import SYSTEM_TENANT_ID
from src.domain.shared.exceptions import EntityNotFoundError
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeDocumentRepo,
    FakeKbRepo,
    make_chunk,
    make_doc,
    make_kb,
)


def _run(coro):
    # fresh loop 避免測試間 pollution（同 reprocess_image_ocr_regression 修法）
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _seed(tenant_id="t-1", kb_id="kb-1", n=3):
    doc_repo = FakeDocumentRepo()
    kb_repo = FakeKbRepo()
    _run(kb_repo.save(make_kb(kb_id, tenant_id)))
    _run(doc_repo.save(make_doc("doc-1", kb_id, tenant_id)))
    _run(
        doc_repo.save_chunks(
            [make_chunk(f"c-{i}", "doc-1", tenant_id) for i in range(n)]
        )
    )
    return doc_repo, kb_repo


def test_system_admin_can_view_any_tenant_kb_chunks():
    """system_admin (SYSTEM_TENANT_ID) 必須能看任意租戶 KB chunks。"""
    doc_repo, kb_repo = _seed(tenant_id="tenant-A", kb_id="kb-A", n=5)
    uc = ListKbChunksUseCase(document_repo=doc_repo, kb_repo=kb_repo)

    # SYSTEM_TENANT_ID 來訪 tenant-A 的 KB
    result = _run(
        uc.execute(
            ListKbChunksQuery(
                kb_id="kb-A",
                tenant_id=SYSTEM_TENANT_ID,
            )
        )
    )
    assert result.total == 5
    assert len(result.items) == 5


def test_tenant_admin_cross_tenant_still_blocked():
    """非 system_admin（普通 tenant）跨租戶仍應 404。"""
    doc_repo, kb_repo = _seed(tenant_id="tenant-A", kb_id="kb-A", n=3)
    uc = ListKbChunksUseCase(document_repo=doc_repo, kb_repo=kb_repo)

    with pytest.raises(EntityNotFoundError):
        _run(
            uc.execute(
                ListKbChunksQuery(
                    kb_id="kb-A",
                    tenant_id="tenant-B",  # 不同租戶 — 不可越權
                )
            )
        )


def test_tenant_admin_own_kb_works():
    """同租戶 access 自己的 KB 仍正常（regression baseline）。"""
    doc_repo, kb_repo = _seed(tenant_id="tenant-A", kb_id="kb-A", n=2)
    uc = ListKbChunksUseCase(document_repo=doc_repo, kb_repo=kb_repo)

    result = _run(
        uc.execute(
            ListKbChunksQuery(kb_id="kb-A", tenant_id="tenant-A")
        )
    )
    assert result.total == 2


def test_system_admin_kb_not_found_still_404():
    """system_admin 訪問不存在的 KB 仍應 404（避免吞錯）。"""
    _, kb_repo = _seed()
    doc_repo = FakeDocumentRepo()  # empty
    uc = ListKbChunksUseCase(document_repo=doc_repo, kb_repo=kb_repo)

    with pytest.raises(EntityNotFoundError):
        _run(
            uc.execute(
                ListKbChunksQuery(
                    kb_id="kb-does-not-exist",
                    tenant_id=SYSTEM_TENANT_ID,
                )
            )
        )
