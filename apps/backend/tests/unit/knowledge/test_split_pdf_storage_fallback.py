"""split_pdf 儲存端故障的資料庫副本保底（2026-09-08 回歸）

POC VM worker 的服務帳號對文件桶無 storage.objects.get / create：
- 讀父 PDF 403 → 過去整份失敗；現在有 DB 副本就繼續拆頁
- 寫子頁 PNG 403 → 過去 loop 直接炸；現在子頁 raw_content 留 DB、storage_path 空
"""

import asyncio
from unittest.mock import AsyncMock, patch

from src.application.knowledge.split_pdf_use_case import SplitPdfUseCase
from src.domain.knowledge.entity import Document
from src.domain.knowledge.value_objects import DocumentId


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _parent(raw: bytes) -> Document:
    return Document(
        id=DocumentId(value="parent-1"), kb_id="kb-1", tenant_id="t1",
        filename="dm.pdf", content_type="application/pdf", content="",
        raw_content=raw, storage_path="t1/parent-1/dm.pdf", status="pending",
    )


def _use_case(parent: Document, storage: AsyncMock):
    doc_repo = AsyncMock()
    doc_repo.find_by_id = AsyncMock(return_value=parent)
    task_repo = AsyncMock()
    uc = SplitPdfUseCase(
        document_repository=doc_repo,
        knowledge_base_repository=AsyncMock(),
        processing_task_repository=task_repo,
        document_file_storage=storage,
    )
    return uc, doc_repo, task_repo


def test_load_403_falls_back_to_db_copy_and_splits_pages():
    storage = AsyncMock()
    storage.load = AsyncMock(
        side_effect=RuntimeError("403 storage.objects.get denied")
    )
    storage.save = AsyncMock(return_value="t1/child/page_001.png")
    parent = _parent(b"%PDF-fake")
    uc, doc_repo, task_repo = _use_case(parent, storage)
    with (
        patch(
            "src.application.knowledge.split_pdf_use_case.count_pages", return_value=2
        ),
        patch(
            "src.application.knowledge.split_pdf_use_case.iter_pages_as_images",
            return_value=iter([b"png1", b"png2"]),
        ),
        patch("src.infrastructure.queue.arq_pool.enqueue", new=AsyncMock()) as enq,
    ):
        _run(uc.execute("parent-1", "task-1"))
    saved = [c.args[0] for c in doc_repo.save.call_args_list]
    assert len(saved) == 2 and all(d.parent_id == "parent-1" for d in saved)
    assert enq.await_count == 2
    statuses = [c.args[1] for c in doc_repo.update_status.call_args_list]
    assert "failed" not in statuses


def test_load_403_without_db_copy_fails():
    storage = AsyncMock()
    storage.load = AsyncMock(side_effect=RuntimeError("403"))
    parent = _parent(b"")
    uc, doc_repo, task_repo = _use_case(parent, storage)
    with patch("src.infrastructure.queue.arq_pool.enqueue", new=AsyncMock()):
        _run(uc.execute("parent-1", "task-1"))
    doc_repo.update_status.assert_any_call("parent-1", "failed")


def test_child_save_403_keeps_png_in_db_copy():
    storage = AsyncMock()
    storage.load = AsyncMock(return_value=b"%PDF-fake")
    storage.save = AsyncMock(
        side_effect=RuntimeError("403 storage.objects.create denied")
    )
    parent = _parent(b"%PDF-fake")
    uc, doc_repo, task_repo = _use_case(parent, storage)
    with (
        patch(
            "src.application.knowledge.split_pdf_use_case.count_pages", return_value=1
        ),
        patch(
            "src.application.knowledge.split_pdf_use_case.iter_pages_as_images",
            return_value=iter([b"png-bytes"]),
        ),
        patch("src.infrastructure.queue.arq_pool.enqueue", new=AsyncMock()),
    ):
        _run(uc.execute("parent-1", "task-1"))
    child = doc_repo.save.call_args_list[0].args[0]
    assert child.storage_path == "" and child.raw_content == b"png-bytes"
    task_repo.update_status.assert_any_call("task-1", "completed", progress=100)
