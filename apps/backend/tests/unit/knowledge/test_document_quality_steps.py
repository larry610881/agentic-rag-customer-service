"""文件品質指標 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.get_document_chunks_use_case import (
    GetDocumentChunksUseCase,
)
from src.application.knowledge.process_document_use_case import (
    ProcessDocumentUseCase,
)
from src.application.knowledge.reprocess_document_use_case import (
    ReprocessDocumentUseCase,
)
from src.domain.knowledge.entity import Chunk, Document
from src.domain.knowledge.services import ChunkQualityService
from src.domain.knowledge.value_objects import ChunkId, DocumentId

scenarios("unit/knowledge/document_quality.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# --- Quality Calculation Scenarios ---


@given("一組正常品質的 chunks")
def normal_chunks(context):
    context["chunks"] = [
        Chunk(content="這是一段完整的正常句子，長度足夠。" * 3, chunk_index=i)
        for i in range(5)
    ]


@given("一組有超過 20% 過短的 chunks")
def too_short_chunks(context):
    # 2/5 = 40% are short (> 20%), but all end with sentence-ending punctuation
    chunks = [
        Chunk(content="短。", chunk_index=0),
        Chunk(content="也短。", chunk_index=1),
        Chunk(content="這是一段完整的正常句子，長度足夠。" * 3, chunk_index=2),
        Chunk(content="這是另一段完整的正常句子，長度足夠。" * 3, chunk_index=3),
        Chunk(content="這是再一段完整的正常句子，長度足夠。" * 3, chunk_index=4),
    ]
    context["chunks"] = chunks


@given("一組有超過 30% 斷句不完整的 chunks")
def mid_sentence_chunks(context):
    # 2/5 = 40% don't end with sentence-ending punctuation (> 30%)
    context["chunks"] = [
        Chunk(content="這是一段完整的句子。" * 5, chunk_index=0),
        Chunk(content="這段沒有結尾標點" + "x" * 50, chunk_index=1),
        Chunk(content="這段也沒結尾標點" + "y" * 50, chunk_index=2),
        Chunk(content="這是正常結尾的句子。" * 5, chunk_index=3),
        Chunk(content="這也是正常的結尾！" * 5, chunk_index=4),
    ]


@given("一組有高變異度的 chunks")
def high_variance_chunks(context):
    # max/avg > 3.0, no chunks < 50 chars, all end with "。"
    short = "這是一段正常長度的完整句子。" * 5  # ~65 chars
    long = "這是一段非常非常非常長的句子內容用來測試。" * 50  # ~950 chars
    # avg ≈ (65*4 + 950)/5 = 1210/5 = 242, max/avg ≈ 950/242 ≈ 3.9 > 3.0
    context["chunks"] = [
        Chunk(content=short, chunk_index=0),
        Chunk(content=short, chunk_index=1),
        Chunk(content=short, chunk_index=2),
        Chunk(content=short, chunk_index=3),
        Chunk(content=long, chunk_index=4),
    ]


@given("一組有過短且斷句不完整的 chunks")
def short_and_mid_sentence_chunks(context):
    # > 20% short + > 30% mid-sentence
    context["chunks"] = [
        Chunk(content="短", chunk_index=0),  # short + mid-sentence
        Chunk(content="也短", chunk_index=1),  # short + mid-sentence
        Chunk(content="不完整斷句" + "z" * 50, chunk_index=2),  # mid-sentence
        Chunk(content="正常結尾的足夠長度句子。" * 5, chunk_index=3),
        Chunk(content="正常結尾的足夠長度句子！" * 5, chunk_index=4),
    ]


@given("空的 chunks 列表")
def empty_chunks(context):
    context["chunks"] = []


@when("計算品質分數")
def calculate_quality(context):
    context["quality"] = ChunkQualityService.calculate(context["chunks"])


@then(parsers.parse("品質分數應為 {score:g}"))
def quality_score_is(context, score):
    assert context["quality"].score == pytest.approx(score, abs=0.01)


@then("品質問題列表應為空")
def no_quality_issues(context):
    assert len(context["quality"].issues) == 0


@then(parsers.parse('品質問題應包含 "{issue}"'))
def quality_issues_contain(context, issue):
    assert issue in context["quality"].issues


# --- Process Document with Quality ---


@given("一個待處理的文件和處理任務（含品質計算）")
def pending_doc_with_quality(context):
    doc = Document(
        id=DocumentId(value="doc-q1"),
        kb_id="kb-001",
        tenant_id="tenant-001",
        filename="test.txt",
        content_type="text/plain",
        content="Test content for quality. " * 20,
        status="pending",
    )
    mock_doc_repo = AsyncMock()
    mock_doc_repo.find_by_id = AsyncMock(return_value=doc)
    mock_doc_repo.update_status = AsyncMock()
    mock_doc_repo.update_quality = AsyncMock()

    chunks = [
        Chunk(
            id=ChunkId(),
            document_id="doc-q1",
            tenant_id="tenant-001",
            content=f"Quality chunk content number {i}. " * 5,
            chunk_index=i,
        )
        for i in range(3)
    ]
    mock_splitter = MagicMock()
    mock_splitter.split.return_value = chunks

    mock_chunk_repo = AsyncMock()
    mock_chunk_repo.save_batch = AsyncMock()

    mock_task_repo = AsyncMock()
    mock_task_repo.update_status = AsyncMock()

    mock_embedding = AsyncMock()
    mock_embedding.embed_texts = AsyncMock(
        return_value=[[0.1] * 1536 for _ in range(3)]
    )

    mock_vector_store = AsyncMock()
    mock_vector_store.ensure_collection = AsyncMock()
    mock_vector_store.upsert = AsyncMock()

    context["use_case"] = ProcessDocumentUseCase(
        document_repository=mock_doc_repo,
        chunk_repository=mock_chunk_repo,
        processing_task_repository=mock_task_repo,
        text_splitter_service=mock_splitter,
        embedding_service=mock_embedding,
        vector_store=mock_vector_store,
    )
    context["mock_doc_repo"] = mock_doc_repo
    context["doc_id"] = "doc-q1"
    context["task_id"] = "task-q1"


@when("執行文件處理（含品質計算）")
def do_process_with_quality(context):
    _run(context["use_case"].execute(context["doc_id"], context["task_id"]))


@then("品質分數應已儲存至文件")
def quality_saved(context):
    context["mock_doc_repo"].update_quality.assert_called_once()
    call_kwargs = context["mock_doc_repo"].update_quality.call_args
    assert call_kwargs.kwargs["quality_score"] > 0 or call_kwargs[0][1] > 0


# --- Paginated Chunk Query ---


@given(parsers.parse("一個文件有 {count:d} 個 chunks"))
def doc_with_n_chunks(context, count):
    chunks = [
        Chunk(
            id=ChunkId(value=f"chunk-{i}"),
            document_id="doc-page",
            tenant_id="tenant-001",
            content=f"Chunk content {i}. " * 10,
            chunk_index=i,
        )
        for i in range(count)
    ]
    mock_chunk_repo = AsyncMock()
    mock_chunk_repo.find_by_document_paginated = AsyncMock(return_value=chunks[:2])
    mock_chunk_repo.count_by_document = AsyncMock(return_value=count)

    context["chunk_use_case"] = GetDocumentChunksUseCase(
        chunk_repository=mock_chunk_repo
    )
    context["doc_id"] = "doc-page"
    context["total_count"] = count


@when(parsers.parse("分頁查詢第 {page:d} 頁每頁 {size:d} 個"))
def paginated_query(context, page, size):
    offset = (page - 1) * size
    context["result"] = _run(
        context["chunk_use_case"].execute(context["doc_id"], limit=size, offset=offset)
    )


@then(parsers.parse("應回傳 {count:d} 個 chunks 且總數為 {total:d}"))
def verify_paginated(context, count, total):
    assert len(context["result"].chunks) == count
    assert context["result"].total == total


# --- Reprocess Document ---


@given("一個已處理的文件")
def processed_doc(context):
    doc = Document(
        id=DocumentId(value="doc-reprocess"),
        kb_id="kb-001",
        tenant_id="tenant-001",
        filename="reprocess.txt",
        content_type="text/plain",
        content="Content for reprocessing. " * 20,
        status="processed",
        chunk_count=3,
    )
    mock_doc_repo = AsyncMock()
    mock_doc_repo.find_by_id = AsyncMock(return_value=doc)
    mock_doc_repo.update_status = AsyncMock()
    mock_doc_repo.update_quality = AsyncMock()

    mock_chunk_repo = AsyncMock()
    mock_chunk_repo.delete_by_document = AsyncMock()
    mock_chunk_repo.save_batch = AsyncMock()

    new_chunks = [
        Chunk(
            id=ChunkId(),
            document_id="doc-reprocess",
            tenant_id="tenant-001",
            content=f"New chunk {i}. " * 10,
            chunk_index=i,
        )
        for i in range(4)
    ]
    mock_splitter = MagicMock()
    mock_splitter.split.return_value = new_chunks

    mock_task_repo = AsyncMock()
    mock_embedding = AsyncMock()
    mock_embedding.embed_texts = AsyncMock(
        return_value=[[0.1] * 1536 for _ in range(4)]
    )

    mock_vector_store = AsyncMock()
    mock_vector_store.delete = AsyncMock()
    mock_vector_store.ensure_collection = AsyncMock()
    mock_vector_store.upsert = AsyncMock()

    context["reprocess_use_case"] = ReprocessDocumentUseCase(
        document_repository=mock_doc_repo,
        chunk_repository=mock_chunk_repo,
        processing_task_repository=mock_task_repo,
        text_splitter_service=mock_splitter,
        embedding_service=mock_embedding,
        vector_store=mock_vector_store,
    )
    context["mock_doc_repo"] = mock_doc_repo
    context["mock_chunk_repo"] = mock_chunk_repo
    context["mock_vector_store"] = mock_vector_store
    context["doc_id"] = "doc-reprocess"


@when("執行重新處理")
def do_reprocess(context):
    _run(context["reprocess_use_case"].execute(context["doc_id"]))


@then("舊 chunks 應被刪除")
def old_chunks_deleted(context):
    context["mock_chunk_repo"].delete_by_document.assert_called_once_with("doc-reprocess")


@then("新 chunks 應被建立")
def new_chunks_created(context):
    context["mock_chunk_repo"].save_batch.assert_called_once()
    saved_chunks = context["mock_chunk_repo"].save_batch.call_args[0][0]
    assert len(saved_chunks) == 4


@then("品質分數應已重新計算")
def quality_recalculated(context):
    context["mock_doc_repo"].update_quality.assert_called_once()
