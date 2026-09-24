"""Bulk ingest 去重以文件 id 刪除（#469963）。

競態本身（新版先處理完才 drain）由整合測試 bulk_ingest.feature 以真實 outbox/drain 驗；
這裡驗 use case 的編排：先上傳、再以舊文件 id 走 DeleteDocumentUseCase，失敗不擴散。
"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.knowledge.bulk_ingest_use_case import (
    BulkIngestCommand,
    BulkIngestItem,
    BulkIngestUseCase,
)
from src.application.knowledge.delete_document_use_case import DeleteDocumentUseCase
from src.application.knowledge.upload_document_use_case import UploadDocumentUseCase
from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.repository import (
    DocumentRepository,
    KnowledgeBaseRepository,
)
from src.domain.knowledge.value_objects import KnowledgeBaseId
from src.domain.shared.exceptions import EntityNotFoundError


@pytest.fixture(autouse=True)
def _no_queue(monkeypatch):
    import src.infrastructure.queue.arq_pool as arq_pool

    monkeypatch.setattr(arq_pool, "enqueue", AsyncMock())


def _kb(tenant_id="t1"):
    now = datetime.now(timezone.utc)
    return KnowledgeBase(
        id=KnowledgeBaseId(value="kb1"),
        tenant_id=tenant_id,
        name="kb",
        description="",
        kb_type="user",
        created_at=now,
        updated_at=now,
    )


def _setup(old_ids=("old-1",), kb_tenant="t1"):
    calls: list[str] = []
    kb_repo = AsyncMock(spec=KnowledgeBaseRepository)
    kb_repo.find_by_id = AsyncMock(return_value=_kb(kb_tenant))
    doc_repo = AsyncMock(spec=DocumentRepository)
    doc_repo.find_top_level_ids_by_source = AsyncMock(return_value=list(old_ids))
    upload = AsyncMock(spec=UploadDocumentUseCase)

    async def _upload(cmd):
        calls.append("upload")
        return SimpleNamespace(
            document=SimpleNamespace(id=SimpleNamespace(value="new-1")),
            task=SimpleNamespace(id=SimpleNamespace(value="task-1")),
        )

    upload.execute = AsyncMock(side_effect=_upload)
    delete = AsyncMock(spec=DeleteDocumentUseCase)

    async def _delete(doc_id, kb_id=None):
        calls.append(f"delete:{doc_id}:{kb_id}")

    delete.execute = AsyncMock(side_effect=_delete)
    uc = BulkIngestUseCase(
        upload_use_case=upload,
        delete_document_use_case=delete,
        kb_repository=kb_repo,
        document_repository=doc_repo,
    )
    return uc, calls, doc_repo, upload, delete


def _cmd(metadata=None):
    meta = (
        {"source": "audit_log", "source_id": "12345"} if metadata is None else metadata
    )
    return BulkIngestCommand(
        kb_id="kb1",
        tenant_id="t1",
        documents=[BulkIngestItem(content="body", filename="f", metadata=meta)],
    )


def test_先上傳新版再以舊文件_id_刪除():
    uc, calls, doc_repo, _, _ = _setup(old_ids=("old-1", "old-2"))
    result = asyncio.run(uc.execute(_cmd()))
    assert result.indexed == 1
    assert calls == ["upload", "delete:old-1:kb1", "delete:old-2:kb1"]
    doc_repo.find_top_level_ids_by_source.assert_awaited_once_with(
        "kb1", "t1", "audit_log", "12345"
    )


def test_上傳失敗時不刪舊版():
    uc, _, _, upload, delete = _setup()
    upload.execute = AsyncMock(side_effect=RuntimeError("boom"))
    result = asyncio.run(uc.execute(_cmd()))
    assert result.failed == 1
    delete.execute.assert_not_awaited()


def test_無_source_不查也不刪():
    uc, calls, doc_repo, _, _ = _setup()
    asyncio.run(uc.execute(_cmd(metadata={})))
    doc_repo.find_top_level_ids_by_source.assert_not_awaited()
    assert calls == ["upload"]


def test_查舊版或刪舊版失敗都不影響新版_accepted():
    uc, _, doc_repo, _, delete = _setup()
    doc_repo.find_top_level_ids_by_source = AsyncMock(side_effect=RuntimeError("db"))
    assert asyncio.run(uc.execute(_cmd())).indexed == 1
    delete.execute.assert_not_awaited()

    uc, _, _, _, delete = _setup(old_ids=("gone", "old-2"))
    delete.execute = AsyncMock(
        side_effect=[EntityNotFoundError("Document", "gone"), RuntimeError("x")]
    )
    assert asyncio.run(uc.execute(_cmd())).indexed == 1
    assert delete.execute.await_count == 2


def test_跨租戶_KB_全部失敗且不查不刪不上傳():
    uc, calls, doc_repo, upload, _ = _setup(kb_tenant="other")
    result = asyncio.run(uc.execute(_cmd()))
    assert (result.indexed, result.failed) == (0, 1)
    assert result.results[0].status == "failed"
    doc_repo.find_top_level_ids_by_source.assert_not_awaited()
    upload.execute.assert_not_awaited()
    assert calls == []
