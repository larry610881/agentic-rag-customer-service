"""Regression test: background task 必須 lazy resolve use case，不能使用 request-scoped session。

根因：upload_document / batch_reprocess / reprocess_document 的 background task
使用了注入的 use case（持有 request-scoped session），但 response 送回後 session 已被
SessionCleanupMiddleware 關閉，導致 DB 操作失敗，文件永遠卡在 "processing"。

修復：background task callback 內從 Container 重新解析 use case。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("unit/knowledge/document_background_session.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given("一個文件上傳端點的 background task callback")
def given_upload_callback(context):
    """從 document_router 模組取得 upload_document 函數。"""
    context["endpoint"] = "upload_document"


@given("一個批次重處理端點的 background task callback")
def given_batch_reprocess_callback(context):
    context["endpoint"] = "batch_reprocess_documents"


@given("一個重處理端點的 background task callback")
def given_reprocess_callback(context):
    context["endpoint"] = "reprocess_document"


@when("background task 被觸發時", target_fixture="captured_task")
def when_background_task_triggered(context):
    """驗證 background task callback 中呼叫 Container 解析 use case。

    策略：mock BackgroundTasks.add_task，攔截傳入的 callback，
    然後執行它並驗證 Container 被呼叫。
    """
    from src.interfaces.api.document_router import (
        batch_reprocess_documents,
        reprocess_document,
        upload_document,
    )

    captured = {"task_fn": None, "task_args": None}

    # Mock BackgroundTasks to capture the callback
    mock_bg = MagicMock()

    def capture_add_task(fn, *args, **kwargs):
        captured["task_fn"] = fn
        captured["task_args"] = args
        captured["task_kwargs"] = kwargs

    mock_bg.add_task = capture_add_task

    endpoint = context["endpoint"]

    if endpoint == "upload_document":
        # Mock upload use case
        mock_upload_uc = AsyncMock()
        mock_result = MagicMock()
        mock_result.document.id.value = "doc-123"
        mock_result.document.kb_id = "kb-1"
        mock_result.document.tenant_id = "t-1"
        mock_result.document.filename = "test.json"
        mock_result.document.content_type = "application/json"
        mock_result.document.status = "processing"
        mock_result.document.chunk_count = 0
        mock_result.document.avg_chunk_length = 0
        mock_result.document.min_chunk_length = 0
        mock_result.document.max_chunk_length = 0
        mock_result.document.quality_score = 0.0
        mock_result.document.quality_issues = []
        mock_result.document.created_at.isoformat.return_value = "2026-03-20T00:00:00"
        mock_result.document.updated_at.isoformat.return_value = "2026-03-20T00:00:00"
        mock_result.task.id.value = "task-123"
        mock_upload_uc.execute.return_value = mock_result

        mock_file = AsyncMock()
        mock_file.read.return_value = b'{"key": "value"}'
        mock_file.content_type = "application/json"
        mock_file.filename = "test.json"

        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "t-1"

        _run(upload_document(
            kb_id="kb-1",
            file=mock_file,
            background_tasks=mock_bg,
            tenant=mock_tenant,
            use_case=mock_upload_uc,
        ))

    elif endpoint == "batch_reprocess_documents":
        mock_reprocess_uc = AsyncMock()
        mock_task = MagicMock()
        mock_task.id.value = "task-456"
        mock_reprocess_uc.begin_reprocess.return_value = mock_task

        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "t-1"

        from src.interfaces.api.document_router import BatchDocIdsRequest

        _run(batch_reprocess_documents(
            kb_id="kb-1",
            body=BatchDocIdsRequest(doc_ids=["doc-1"]),
            background_tasks=mock_bg,
            tenant=mock_tenant,
            use_case=mock_reprocess_uc,
        ))

    elif endpoint == "reprocess_document":
        mock_reprocess_uc = AsyncMock()
        mock_task = MagicMock()
        mock_task.id.value = "task-789"
        mock_reprocess_uc.begin_reprocess.return_value = mock_task

        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "t-1"

        from src.interfaces.api.document_router import ReprocessRequest

        _run(reprocess_document(
            kb_id="kb-1",
            doc_id="doc-1",
            body=ReprocessRequest(),
            background_tasks=mock_bg,
            tenant=mock_tenant,
            use_case=mock_reprocess_uc,
        ))

    return captured


@then("callback 應從 Container 重新解析 use case 而非使用注入的實例")
def then_lazy_resolve(captured_task):
    """驗證 background task callback 呼叫了 Container 來解析 use case。

    safe_background_task 是第一個 arg，真正的 callback 是第二個 arg。
    執行 callback 並檢查 Container 方法被呼叫。
    """
    from src.infrastructure.logging.error_handler import safe_background_task

    assert captured_task["task_fn"] is safe_background_task, (
        "Background task should use safe_background_task wrapper"
    )

    # The actual coroutine function is the first positional arg to safe_background_task
    actual_fn = captured_task["task_args"][0]

    # Patch Container to verify lazy resolution
    with patch(
        "src.interfaces.api.document_router.Container"
    ) as mock_container:
        mock_uc = AsyncMock()
        mock_container.process_document_use_case.return_value = mock_uc
        mock_container.reprocess_document_use_case.return_value = mock_uc

        # Execute the callback — it should call Container to get a fresh use case
        remaining_args = captured_task["task_args"][1:]
        _run(actual_fn(*remaining_args))

        # At least one Container resolution should have happened
        container_called = (
            mock_container.process_document_use_case.called
            or mock_container.reprocess_document_use_case.called
        )
        assert container_called, (
            "Background task callback must resolve use case from Container "
            "(lazy resolve), not use the injected request-scoped instance"
        )
