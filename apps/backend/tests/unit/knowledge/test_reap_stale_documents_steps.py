"""BDD: unit/knowledge/reap_stale_documents.feature"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.reap_stale_documents_use_case import (
    ReapStaleDocumentsUseCase,
)
from src.domain.knowledge.entity import Document, ProcessingTask
from src.domain.knowledge.value_objects import DocumentId, ProcessingTaskId

scenarios("unit/knowledge/reap_stale_documents.feature")


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {"grace_minutes": 15, "queue_depth": 0, "task": None}


@given(parsers.parse("逾時門檻為 {minutes:d} 分鐘"))
def _grace(ctx, minutes):
    ctx["grace_minutes"] = minutes


@given(parsers.parse('文件 "{doc_id}" 狀態為 pending 且已建立 {age:d} 分鐘'))
def _stale_doc(ctx, doc_id, age):
    created = datetime.now(timezone.utc) - timedelta(minutes=age)
    doc = Document(
        id=DocumentId(doc_id),
        kb_id="kb-1",
        tenant_id="T001",
        filename="a.pdf",
        status="pending",
        created_at=created,
        updated_at=created,
    )
    ctx["doc"] = doc
    ctx["task"] = ProcessingTask(
        id=ProcessingTaskId("task-1"), document_id=doc_id, tenant_id="T001"
    )


@given(parsers.parse('文件 "{doc_id}" 沒有對應的處理工作'))
def _no_task(ctx, doc_id):
    ctx["task"] = None


@given(parsers.parse("arq 佇列長度為 {depth:d}"))
def _queue_depth(ctx, depth):
    ctx["queue_depth"] = depth


@when("執行 reap_stale_documents")
def _run(ctx):
    doc = ctx["doc"]
    doc_repo = AsyncMock()
    # 只有超過門檻的才會被 repo 撈出來，測試裡直接依門檻模擬 SQL 的行為
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ctx["grace_minutes"])
    doc_repo.find_stale_pending.return_value = (
        [doc] if doc.created_at <= cutoff else []
    )
    task_repo = AsyncMock()
    task_repo.find_by_document_id.return_value = ctx["task"]

    use_case = ReapStaleDocumentsUseCase(
        doc_repo, task_repo, grace_minutes=ctx["grace_minutes"]
    )
    ctx["result"] = run(use_case.execute(queue_depth=ctx["queue_depth"]))
    ctx["doc_repo"] = doc_repo
    ctx["task_repo"] = task_repo


@then(parsers.parse('文件 "{doc_id}" 狀態應為 failed'))
def _failed(ctx, doc_id):
    ctx["doc_repo"].update_status.assert_awaited_once_with(doc_id, "failed")


@then(parsers.parse('文件 "{doc_id}" 狀態應維持 pending'))
def _still_pending(ctx, doc_id):
    ctx["doc_repo"].update_status.assert_not_awaited()


@then(parsers.parse('文件 "{doc_id}" 的處理工作應記錄錯誤訊息含 "{needle}"'))
def _task_message(ctx, doc_id, needle):
    ctx["task_repo"].update_status.assert_awaited_once()
    kwargs = ctx["task_repo"].update_status.await_args.kwargs
    assert needle in kwargs["error_message"]
