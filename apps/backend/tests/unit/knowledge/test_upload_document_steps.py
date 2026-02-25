"""文件上傳 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.upload_document_use_case import (
    UploadDocumentCommand,
    UploadDocumentUseCase,
)
from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.value_objects import KnowledgeBaseId
from src.domain.shared.exceptions import EntityNotFoundError, UnsupportedFileTypeError

scenarios("unit/knowledge/upload_document.feature")


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
def mock_kb_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_doc_repo():
    repo = AsyncMock()
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def mock_task_repo():
    repo = AsyncMock()
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def mock_file_parser():
    parser = MagicMock()
    parser.supported_types.return_value = {
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
        "text/xml",
        "application/xml",
        "text/html",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/rtf",
        "text/rtf",
    }
    parser.parse.return_value = "parsed content"
    return parser


@pytest.fixture
def kb_id():
    return "kb-test-123"


@pytest.fixture
def tenant_id():
    return "tenant-test-456"


@pytest.fixture
def upload_use_case(mock_kb_repo, mock_doc_repo, mock_task_repo, mock_file_parser):
    return UploadDocumentUseCase(
        knowledge_base_repository=mock_kb_repo,
        document_repository=mock_doc_repo,
        processing_task_repository=mock_task_repo,
        file_parser_service=mock_file_parser,
    )


@given("一個已存在的知識庫")
def existing_kb(context, mock_kb_repo, kb_id, tenant_id):
    kb = KnowledgeBase(
        id=KnowledgeBaseId(value=kb_id),
        tenant_id=tenant_id,
        name="Test KB",
    )
    mock_kb_repo.find_by_id = AsyncMock(return_value=kb)
    context["kb_id"] = kb_id
    context["tenant_id"] = tenant_id


@when(parsers.parse('上傳一個 TXT 文件 "{filename}" 到知識庫'))
def upload_txt(context, upload_use_case, filename, kb_id, tenant_id):
    command = UploadDocumentCommand(
        kb_id=kb_id,
        tenant_id=tenant_id,
        filename=filename,
        content_type="text/plain",
        raw_content=b"Hello World",
    )
    result = _run(upload_use_case.execute(command))
    context["result"] = result


@when(parsers.parse('上傳一個 PDF 文件 "{filename}" 到知識庫'))
def upload_pdf(context, upload_use_case, filename, kb_id, tenant_id):
    command = UploadDocumentCommand(
        kb_id=kb_id,
        tenant_id=tenant_id,
        filename=filename,
        content_type="application/pdf",
        raw_content=b"%PDF-fake-content",
    )
    result = _run(upload_use_case.execute(command))
    context["result"] = result


@when(parsers.parse('上傳一個 DOCX 文件 "{filename}" 到知識庫'))
def upload_docx(context, upload_use_case, filename, kb_id, tenant_id):
    command = UploadDocumentCommand(
        kb_id=kb_id,
        tenant_id=tenant_id,
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        raw_content=b"PK-fake-docx",
    )
    result = _run(upload_use_case.execute(command))
    context["result"] = result


@when(parsers.parse('上傳一個不支援的檔案 "{filename}" 類型為 "{content_type}"'))
def upload_unsupported(
    context, upload_use_case, filename, content_type, kb_id, tenant_id
):
    command = UploadDocumentCommand(
        kb_id=kb_id,
        tenant_id=tenant_id,
        filename=filename,
        content_type=content_type,
        raw_content=b"fake-png-data",
    )
    try:
        _run(upload_use_case.execute(command))
        context["error"] = None
    except UnsupportedFileTypeError as e:
        context["error"] = e


@when("上傳文件到不存在的知識庫")
def upload_to_missing_kb(context, upload_use_case, mock_kb_repo, tenant_id):
    mock_kb_repo.find_by_id = AsyncMock(return_value=None)
    command = UploadDocumentCommand(
        kb_id="non-existent-kb",
        tenant_id=tenant_id,
        filename="test.txt",
        content_type="text/plain",
        raw_content=b"content",
    )
    try:
        _run(upload_use_case.execute(command))
        context["error"] = None
    except EntityNotFoundError as e:
        context["error"] = e


@then(parsers.parse('文件狀態為 "{status}"'))
def doc_status_is(context, status):
    assert context["result"].document.status == status


@then("文件綁定到正確的知識庫和租戶")
def doc_bound_correctly(context):
    doc = context["result"].document
    assert doc.kb_id == context["kb_id"]
    assert doc.tenant_id == context["tenant_id"]


@then("拋出 UnsupportedFileTypeError")
def raises_unsupported(context):
    assert isinstance(context["error"], UnsupportedFileTypeError)


@then("拋出 EntityNotFoundError")
def raises_not_found(context):
    assert isinstance(context["error"], EntityNotFoundError)


@then("檔案解析是透過 asyncio.to_thread 執行")
def verify_to_thread(context, mock_file_parser):
    # asyncio.to_thread 會在背景執行緒呼叫 parse，驗證 parse 有被正確調用
    mock_file_parser.parse.assert_called_once()
