"""GetWikiStatusUseCase unit tests — stale detection 邏輯。

驗證 W.4 新增的 stale detection：
1. compiled_at > max_doc_updated_at → 維持 ready
2. compiled_at < max_doc_updated_at → 降級為 stale
3. KB 沒有 documents → 維持原 status（不降級）
4. status 原本是 compiling/pending/failed → 不降級（只對 ready 處理）
5. wiki graph 不存在 → throw EntityNotFoundError
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.application.wiki.get_wiki_status_use_case import (
    GetWikiStatusUseCase,
)
from src.domain.knowledge.repository import DocumentRepository
from src.domain.shared.exceptions import EntityNotFoundError
from src.domain.wiki.entity import WikiGraph
from src.domain.wiki.repository import WikiGraphRepository
from src.domain.wiki.value_objects import WikiGraphId


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def mock_wiki_repo():
    return AsyncMock(spec=WikiGraphRepository)


@pytest.fixture
def mock_doc_repo():
    return AsyncMock(spec=DocumentRepository)


@pytest.fixture
def use_case(mock_wiki_repo, mock_doc_repo):
    return GetWikiStatusUseCase(
        wiki_graph_repository=mock_wiki_repo,
        document_repository=mock_doc_repo,
    )


def _make_ready_graph(compiled_at: datetime) -> WikiGraph:
    return WikiGraph(
        id=WikiGraphId(value="g-001"),
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="ready",
        nodes={"n1": {"label": "x"}},
        edges={},
        clusters=[],
        metadata={"doc_count": 5},
        compiled_at=compiled_at,
    )


def test_ready_status_unchanged_when_no_doc_updates(
    use_case, mock_wiki_repo, mock_doc_repo
):
    """compiled_at > max_doc_updated_at → 維持 ready"""
    compiled_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    older_doc_time = compiled_at - timedelta(hours=1)

    mock_wiki_repo.find_by_bot_id.return_value = _make_ready_graph(compiled_at)
    mock_doc_repo.find_max_updated_at_by_kb.return_value = older_doc_time

    result = _run(use_case.execute(tenant_id="t-001", bot_id="b-001"))

    assert result.status == "ready"
    mock_doc_repo.find_max_updated_at_by_kb.assert_called_once_with(
        "kb-001", "t-001"
    )


def test_ready_status_downgrades_to_stale_when_doc_newer(
    use_case, mock_wiki_repo, mock_doc_repo
):
    """compiled_at < max_doc_updated_at → 降級為 stale"""
    compiled_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    newer_doc_time = compiled_at + timedelta(hours=1)

    mock_wiki_repo.find_by_bot_id.return_value = _make_ready_graph(compiled_at)
    mock_doc_repo.find_max_updated_at_by_kb.return_value = newer_doc_time

    result = _run(use_case.execute(tenant_id="t-001", bot_id="b-001"))

    assert result.status == "stale"


def test_no_documents_in_kb_keeps_ready_status(
    use_case, mock_wiki_repo, mock_doc_repo
):
    """KB 沒有 documents → 維持原 status（不降級）"""
    compiled_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)

    mock_wiki_repo.find_by_bot_id.return_value = _make_ready_graph(compiled_at)
    mock_doc_repo.find_max_updated_at_by_kb.return_value = None

    result = _run(use_case.execute(tenant_id="t-001", bot_id="b-001"))

    assert result.status == "ready"


def test_compiling_status_not_affected_by_doc_updates(
    use_case, mock_wiki_repo, mock_doc_repo
):
    """status=compiling 即使 doc 較新也不降級為 stale"""
    compiled_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    newer_doc_time = compiled_at + timedelta(hours=1)

    graph = WikiGraph(
        id=WikiGraphId(value="g-001"),
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="compiling",
        compiled_at=compiled_at,
    )
    mock_wiki_repo.find_by_bot_id.return_value = graph
    mock_doc_repo.find_max_updated_at_by_kb.return_value = newer_doc_time

    result = _run(use_case.execute(tenant_id="t-001", bot_id="b-001"))

    assert result.status == "compiling"
    # find_max_updated_at_by_kb 不應被呼叫（避免不必要的 DB query）
    mock_doc_repo.find_max_updated_at_by_kb.assert_not_called()


def test_failed_status_not_affected_by_doc_updates(
    use_case, mock_wiki_repo, mock_doc_repo
):
    """status=failed 即使 doc 較新也不降級"""
    compiled_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    newer_doc_time = compiled_at + timedelta(hours=1)

    graph = WikiGraph(
        id=WikiGraphId(value="g-001"),
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="failed",
        compiled_at=compiled_at,
    )
    mock_wiki_repo.find_by_bot_id.return_value = graph
    mock_doc_repo.find_max_updated_at_by_kb.return_value = newer_doc_time

    result = _run(use_case.execute(tenant_id="t-001", bot_id="b-001"))

    assert result.status == "failed"
    mock_doc_repo.find_max_updated_at_by_kb.assert_not_called()


def test_pending_status_not_affected_by_doc_updates(
    use_case, mock_wiki_repo, mock_doc_repo
):
    """status=pending 不降級"""
    graph = WikiGraph(
        id=WikiGraphId(value="g-001"),
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="pending",
        compiled_at=None,
    )
    mock_wiki_repo.find_by_bot_id.return_value = graph

    result = _run(use_case.execute(tenant_id="t-001", bot_id="b-001"))

    assert result.status == "pending"
    mock_doc_repo.find_max_updated_at_by_kb.assert_not_called()


def test_wiki_graph_not_found_raises(use_case, mock_wiki_repo):
    mock_wiki_repo.find_by_bot_id.return_value = None

    with pytest.raises(EntityNotFoundError):
        _run(use_case.execute(tenant_id="t-001", bot_id="b-001"))


def test_compiled_at_none_skips_stale_check(
    use_case, mock_wiki_repo, mock_doc_repo
):
    """status=ready but compiled_at=None (邊緣情況) 不會做 stale check"""
    graph = WikiGraph(
        id=WikiGraphId(value="g-001"),
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="ready",
        compiled_at=None,
    )
    mock_wiki_repo.find_by_bot_id.return_value = graph

    result = _run(use_case.execute(tenant_id="t-001", bot_id="b-001"))

    assert result.status == "ready"
    mock_doc_repo.find_max_updated_at_by_kb.assert_not_called()
