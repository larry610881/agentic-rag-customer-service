"""文件處理 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.get_processing_task_use_case import (
    GetProcessingTaskUseCase,
)
from src.application.knowledge.process_document_use_case import (
    ProcessDocumentUseCase,
)
from src.domain.knowledge.entity import Chunk, Document, ProcessingTask
from src.domain.knowledge.value_objects import (
    ChunkId,
    DocumentId,
    ProcessingTaskId,
)

scenarios("unit/knowledge/process_document.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_doc_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_chunk_repo():
    repo = AsyncMock()
    repo.save_batch = AsyncMock()
    return repo


@pytest.fixture
def mock_task_repo():
    repo = AsyncMock()
    repo.update_status = AsyncMock()
    return repo


@pytest.fixture
def mock_splitter():
    splitter = MagicMock()
    return splitter


@pytest.fixture
def mock_embedding():
    embedding = AsyncMock()
    return embedding


@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    store.ensure_collection = AsyncMock()
    store.upsert = AsyncMock()
    return store


@pytest.fixture
def process_use_case(
    mock_doc_repo,
    mock_chunk_repo,
    mock_task_repo,
    mock_splitter,
    mock_embedding,
    mock_vector_store,
):
    return ProcessDocumentUseCase(
        document_repository=mock_doc_repo,
        chunk_repository=mock_chunk_repo,
        processing_task_repository=mock_task_repo,
        text_splitter_service=mock_splitter,
        embedding_service=mock_embedding,
        vector_store=mock_vector_store,
    )


@given("一個待處理的文件和處理任務")
def pending_document(
    context,
    mock_doc_repo,
    mock_splitter,
    mock_embedding,
):
    doc = Document(
        id=DocumentId(value="doc-001"),
        kb_id="kb-001",
        tenant_id="tenant-001",
        filename="test.txt",
        content_type="text/plain",
        content="This is a long enough text for splitting. " * 20,
        status="pending",
    )
    mock_doc_repo.find_by_id = AsyncMock(return_value=doc)
    mock_doc_repo.update_status = AsyncMock()

    chunks = [
        Chunk(
            id=ChunkId(),
            document_id="doc-001",
            tenant_id="tenant-001",
            content=f"chunk {i}",
            chunk_index=i,
        )
        for i in range(3)
    ]
    mock_splitter.split.return_value = chunks

    mock_embedding.embed_texts = AsyncMock(
        return_value=[[0.1] * 1536 for _ in range(3)]
    )

    context["doc_id"] = "doc-001"
    context["task_id"] = "task-001"
    context["expected_chunks"] = 3


@given("分塊服務會拋出例外")
def splitter_raises(mock_splitter):
    mock_splitter.split.side_effect = RuntimeError(
        "Splitter failed"
    )


@given("一個已存在的處理任務")
def existing_task(context, mock_task_repo):
    task = ProcessingTask(
        id=ProcessingTaskId(value="task-existing"),
        document_id="doc-001",
        tenant_id="tenant-001",
        status="completed",
        progress=100,
    )
    mock_task_repo.find_by_id = AsyncMock(return_value=task)
    context["task_id"] = "task-existing"


@when("執行文件處理")
def do_process(context, process_use_case):
    _run(
        process_use_case.execute(
            context["doc_id"], context["task_id"]
        )
    )


@when("查詢該任務狀態")
def query_task(context, mock_task_repo):
    use_case = GetProcessingTaskUseCase(
        processing_task_repository=mock_task_repo
    )
    context["result"] = _run(
        use_case.execute(context["task_id"])
    )


@then(parsers.parse('任務狀態變為 "{status}"'))
def task_status_is(context, status, mock_task_repo):
    calls = mock_task_repo.update_status.call_args_list
    last_call = calls[-1]
    assert last_call.args[1] == status


@then(parsers.parse('文件狀態變為 "{status}"'))
def doc_status_is(context, status, mock_doc_repo):
    calls = mock_doc_repo.update_status.call_args_list
    last_call = calls[-1]
    assert last_call.args[1] == status


@then("chunk 數量大於 0")
def chunk_count_positive(mock_doc_repo):
    calls = mock_doc_repo.update_status.call_args_list
    # The last doc update should have chunk_count
    last_call = calls[-1]
    chunk_count = last_call.kwargs.get("chunk_count")
    assert chunk_count is not None and chunk_count > 0


@then("任務包含錯誤訊息")
def task_has_error(mock_task_repo):
    calls = mock_task_repo.update_status.call_args_list
    last_call = calls[-1]
    error_msg = last_call.kwargs.get("error_message")
    assert error_msg is not None and len(error_msg) > 0


@then("回傳任務詳細資訊")
def task_details_returned(context):
    result = context["result"]
    assert result is not None
    assert result.id.value == context["task_id"]
    assert result.status == "completed"
