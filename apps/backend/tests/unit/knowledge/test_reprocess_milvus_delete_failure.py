"""Regression test: reprocess Milvus delete failure must propagate.

Bug context (audit 2026-05-06):
    reprocess_document_use_case 的 vector_store.delete 預設 raise_on_error=False
    → Milvus delete 失敗時 swallow + log warning → 緊接著 upsert 新向量 →
    Milvus 內舊 chunks (失敗那筆) + 新 chunks (用新 chunk_id) 共存 →
    search 可能回 phantom 內容（chunk_id 不在 PG 但仍在 Milvus）。

Fix:
    reprocess 的 delete 改用 raise_on_error=True；失敗會走 use case 的
    except Exception → doc.status="failed" + task.error_message 給 user 看。
    不走 outbox（reprocess 必須同步「刪舊→立刻寫新」，async drain 會把剛
    upsert 的新向量也刪掉）。

此檔保證未來再回歸時測試會 fail。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.knowledge.reprocess_document_use_case import (
    ReprocessDocumentUseCase,
)
from src.domain.knowledge.entity import Document, KnowledgeBase
from src.domain.knowledge.value_objects import DocumentId


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_use_case(*, vector_store_delete_raises: bool):
    """Build ReprocessDocumentUseCase + mocked deps."""
    doc_repo = AsyncMock()
    doc_repo.find_by_id = AsyncMock(
        return_value=Document(
            id=DocumentId(value="doc-1"),
            kb_id="kb-1",
            tenant_id="t-1",
            filename="readme.txt",
            content_type="text/plain",
            content="old content",
            raw_content=b"new content from disk",
            storage_path="",
        )
    )
    doc_repo.update_status = AsyncMock()
    doc_repo.update_content = AsyncMock()
    doc_repo.update_quality = AsyncMock()
    doc_repo.delete_chunks_by_document = AsyncMock()
    doc_repo.save_chunks = AsyncMock()

    task_repo = AsyncMock()
    task_repo.update_status = AsyncMock()

    kb_repo = AsyncMock()
    kb_repo.find_by_id = AsyncMock(return_value=KnowledgeBase(ocr_mode="general"))

    splitter = MagicMock()
    splitter.split.return_value = []  # empty chunks shortcut

    embedding = AsyncMock()
    vector_store = AsyncMock()
    if vector_store_delete_raises:
        vector_store.delete = AsyncMock(
            side_effect=ConnectionError("simulated milvus delete failure")
        )
    else:
        vector_store.delete = AsyncMock()
    vector_store.ensure_collection = AsyncMock()
    vector_store.upsert = AsyncMock()

    language_detector = MagicMock()
    language_detector.detect.return_value = "en"
    file_parser = MagicMock()
    file_parser.parse = MagicMock(return_value="parsed content")
    file_storage = AsyncMock()
    file_storage.load = AsyncMock(side_effect=FileNotFoundError)

    use_case = ReprocessDocumentUseCase(
        document_repository=doc_repo,
        processing_task_repository=task_repo,
        knowledge_base_repository=kb_repo,
        text_splitter_service=splitter,
        embedding_service=embedding,
        vector_store=vector_store,
        language_detection_service=language_detector,
        file_parser_service=file_parser,
        document_file_storage=file_storage,
    )
    return use_case, doc_repo, task_repo, vector_store


def test_reprocess_propagates_milvus_delete_failure_then_marks_failed():
    """Milvus delete 失敗時 reprocess 應 raise + doc.status='failed'。

    避免「silent 殘留 + 新向量 upsert 後 search 回 phantom」的核心保護。
    """
    use_case, doc_repo, task_repo, vector_store = _make_use_case(
        vector_store_delete_raises=True,
    )

    # use case 內部 except 會 re-raise（讓 arq retry 接到）→ 測試方要 catch
    with pytest.raises(ConnectionError):
        _run(use_case.execute("doc-1", "task-1"))

    # vector_store.delete 必須帶 raise_on_error=True
    vector_store.delete.assert_called_once()
    call_kwargs = vector_store.delete.call_args.kwargs
    assert call_kwargs.get("raise_on_error") is True, (
        "reprocess 的 vector_store.delete 必須傳 raise_on_error=True，"
        "否則失敗會被 swallow → 殘留舊向量 + 新 upsert 共存 → search phantom"
    )

    # doc.status 應為 failed（最後一次 update_status 呼叫）
    update_status_calls = doc_repo.update_status.call_args_list
    last_status = update_status_calls[-1].args[1]
    seq = [c.args[1] for c in update_status_calls]
    assert last_status == "failed", (
        f"doc.status 應為 failed，實際 update 序列：{seq}"
    )

    # task 也應標 failed 含 error_message
    task_failed_calls = [
        c for c in task_repo.update_status.call_args_list
        if "failed" in str(c)
    ]
    assert task_failed_calls, "task_repo.update_status('failed') 必須被呼叫"
    err_msg = task_failed_calls[-1].kwargs.get("error_message", "")
    assert "milvus" in err_msg.lower() or "ConnectionError" in err_msg

    # 失敗後不應 upsert 新向量（避免新舊混合）
    vector_store.upsert.assert_not_called()


def test_reprocess_milvus_delete_success_continues_pipeline():
    """正常 path: delete 成功時繼續 pipeline，不影響後續 upsert 流程。"""
    use_case, doc_repo, _task_repo, vector_store = _make_use_case(
        vector_store_delete_raises=False,
    )

    _run(use_case.execute("doc-1", "task-1"))

    # delete 仍帶 raise_on_error=True（一致性）
    call_kwargs = vector_store.delete.call_args.kwargs
    assert call_kwargs.get("raise_on_error") is True

    # 因為 splitter 回傳空 chunks，doc 應標 processed (chunk_count=0)
    last_status = doc_repo.update_status.call_args_list[-1].args[1]
    assert last_status == "processed"
