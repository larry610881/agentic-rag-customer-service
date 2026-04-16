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


def _make_doc(i: int, kb_id: str, parent_id: str | None = None) -> Document:
    now = datetime.now(timezone.utc)
    return Document(
        id=DocumentId(value=f"doc-{i}"),
        kb_id=kb_id,
        tenant_id="tenant-001",
        filename=f"file-{i}.txt",
        content_type="text/plain",
        content=f"content {i}",
        status="processed",
        chunk_count=5,
        parent_id=parent_id,
        created_at=now,
        updated_at=now,
    )


@given(parsers.parse('知識庫 "{kb_id}" 有 {count:d} 份已上傳文件'))
def kb_has_documents(context, mock_doc_repo, kb_id, count):
    docs = [_make_doc(i, kb_id) for i in range(count)]
    mock_doc_repo.find_top_level_by_kb = AsyncMock(return_value=docs)
    mock_doc_repo.count_top_level_by_kb = AsyncMock(return_value=count)


@given(parsers.parse('知識庫 "{kb_id}" 有 {parents:d} 份父文件與 {children:d} 份子頁'))
def kb_has_parent_and_children(context, mock_doc_repo, kb_id, parents, children):
    # 僅 top-level 應回傳；子頁不該進列表
    parent_docs = [_make_doc(i, kb_id) for i in range(parents)]
    # 驗證 repo 方法只回傳 top-level（模擬 SQL parent_id IS NULL filter）
    mock_doc_repo.find_top_level_by_kb = AsyncMock(return_value=parent_docs)
    mock_doc_repo.count_top_level_by_kb = AsyncMock(return_value=parents)


@when(parsers.parse('查詢知識庫 "{kb_id}" 的文件列表'), target_fixture="result")
def query_documents(context, list_use_case, mock_doc_repo, kb_id):
    if not hasattr(mock_doc_repo.find_top_level_by_kb, 'return_value') or not isinstance(
        mock_doc_repo.find_top_level_by_kb.return_value, list
    ):
        mock_doc_repo.find_top_level_by_kb = AsyncMock(return_value=[])
        mock_doc_repo.count_top_level_by_kb = AsyncMock(return_value=0)
    context["list_result"] = _run(list_use_case.execute(kb_id))
    context["count_result"] = _run(list_use_case.count(kb_id))
    return context["list_result"]


@then(parsers.parse("應回傳 {count:d} 份文件"))
def should_return_count(result, count):
    assert len(result) == count


@then(parsers.parse("文件總數應為 {count:d}"))
def should_have_total(context, count):
    assert context["count_result"] == count
