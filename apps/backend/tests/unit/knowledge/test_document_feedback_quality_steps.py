"""文件品質回饋關聯統計 BDD Step Definitions"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.get_document_quality_stats_use_case import (
    GetDocumentQualityStatsUseCase,
)
from src.domain.conversation.feedback_analysis_vo import RetrievalQualityRecord
from src.domain.knowledge.entity import Document
from src.domain.knowledge.value_objects import DocumentId

scenarios("unit/knowledge/document_feedback_quality.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given(parsers.parse('知識庫有文件 "{filename}" 且有差評引用其 chunks'))
def doc_with_negative_feedback(context, filename):
    doc = Document(
        id=DocumentId(value="doc-faq"),
        kb_id="kb-001",
        tenant_id="tenant-001",
        filename=filename,
        content_type="text/plain",
        content="FAQ content.",
        status="processed",
        quality_score=0.8,
    )
    mock_doc_repo = AsyncMock()
    mock_doc_repo.find_all_by_kb = AsyncMock(return_value=[doc])

    mock_chunk_repo = AsyncMock()
    mock_chunk_repo.find_chunk_ids_by_kb = AsyncMock(
        return_value={"doc-faq": ["chunk-faq-1", "chunk-faq-2"]}
    )

    negative_record = RetrievalQualityRecord(
        user_question="FAQ 問題",
        assistant_answer="不好的回答",
        retrieved_chunks=[{"chunk_id": "chunk-faq-1", "content": "..."}],
        rating="negative",
        comment="答非所問",
        created_at=datetime.now(timezone.utc),
    )
    mock_feedback_repo = AsyncMock()
    mock_feedback_repo.get_negative_with_context = AsyncMock(
        return_value=[negative_record]
    )

    context["use_case"] = GetDocumentQualityStatsUseCase(
        document_repository=mock_doc_repo,
        chunk_repository=mock_chunk_repo,
        feedback_repository=mock_feedback_repo,
    )
    context["kb_id"] = "kb-001"
    context["tenant_id"] = "tenant-001"
    context["expected_filename"] = filename


@given(parsers.parse('知識庫有文件 "{filename}" 且沒有差評'))
def doc_without_negative_feedback(context, filename):
    doc = Document(
        id=DocumentId(value="doc-guide"),
        kb_id="kb-001",
        tenant_id="tenant-001",
        filename=filename,
        content_type="text/plain",
        content="Guide content.",
        status="processed",
        quality_score=0.9,
    )
    mock_doc_repo = AsyncMock()
    mock_doc_repo.find_all_by_kb = AsyncMock(return_value=[doc])

    mock_chunk_repo = AsyncMock()
    mock_chunk_repo.find_chunk_ids_by_kb = AsyncMock(
        return_value={"doc-guide": ["chunk-guide-1"]}
    )

    mock_feedback_repo = AsyncMock()
    mock_feedback_repo.get_negative_with_context = AsyncMock(return_value=[])

    context["use_case"] = GetDocumentQualityStatsUseCase(
        document_repository=mock_doc_repo,
        chunk_repository=mock_chunk_repo,
        feedback_repository=mock_feedback_repo,
    )
    context["kb_id"] = "kb-001"
    context["tenant_id"] = "tenant-001"
    context["expected_filename"] = filename


@when("查詢品質統計")
def query_quality_stats(context):
    context["result"] = _run(
        context["use_case"].execute(
            context["kb_id"], context["tenant_id"]
        )
    )


@then(parsers.parse('"{filename}" 的 negative_feedback_count 應大於 0'))
def has_negative_feedback(context, filename):
    stat = next(s for s in context["result"] if s.filename == filename)
    assert stat.negative_feedback_count > 0


@then(parsers.parse('"{filename}" 的 negative_feedback_count 應為 0'))
def no_negative_feedback(context, filename):
    stat = next(s for s in context["result"] if s.filename == filename)
    assert stat.negative_feedback_count == 0
