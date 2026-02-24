"""知識庫文件列表 BDD Step Definitions"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.list_documents_use_case import ListDocumentsUseCase
from src.domain.knowledge.entity import Document
from src.domain.knowledge.value_objects import DocumentId

scenarios("unit/knowledge/list_documents.feature")


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
    return AsyncMock()


@pytest.fixture
def list_use_case(mock_doc_repo):
    return ListDocumentsUseCase(document_repository=mock_doc_repo)


@given(parsers.parse('知識庫 "{kb_id}" 存在'))
def kb_exists(context, kb_id):
    context["kb_id"] = kb_id


@given(parsers.parse('知識庫 "{kb_id}" 有 {count:d} 份已上傳文件'))
def kb_has_documents(context, mock_doc_repo, kb_id, count):
    now = datetime.now(timezone.utc)
    docs = [
        Document(
            id=DocumentId(value=f"doc-{i}"),
            kb_id=kb_id,
            tenant_id="tenant-001",
            filename=f"file-{i}.txt",
            content_type="text/plain",
            content=f"content {i}",
            status="processed",
            chunk_count=5,
            created_at=now,
            updated_at=now,
        )
        for i in range(count)
    ]
    mock_doc_repo.find_all_by_kb = AsyncMock(return_value=docs)


@when(parsers.parse('查詢知識庫 "{kb_id}" 的文件列表'), target_fixture="result")
def query_documents(context, list_use_case, mock_doc_repo, kb_id):
    if not mock_doc_repo.find_all_by_kb.called and not isinstance(
        mock_doc_repo.find_all_by_kb.return_value, list
    ):
        mock_doc_repo.find_all_by_kb = AsyncMock(return_value=[])
    return _run(list_use_case.execute(kb_id))


@then(parsers.parse("應回傳 {count:d} 份文件"))
def should_return_count(result, count):
    assert len(result) == count
