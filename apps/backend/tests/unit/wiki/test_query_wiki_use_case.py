"""QueryWikiUseCase unit tests — mock repository + mock navigator.

驗證：
- Strategy dispatch（從 navigators dict 取對應 navigator）
- WikiGraph 不存在 → 可讀錯誤訊息（非 exception）
- WikiGraph status 各種狀態 → 對應錯誤訊息
- Source schema 與 RAGQueryTool 一致
- 未知 strategy → ValidationError
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.application.wiki.query_wiki_use_case import (
    QueryWikiCommand,
    QueryWikiUseCase,
)
from src.domain.shared.exceptions import ValidationError
from src.domain.wiki.entity import WikiGraph
from src.domain.wiki.navigator import GraphNavigator, NavigationResult
from src.domain.wiki.repository import WikiGraphRepository
from src.domain.wiki.value_objects import WikiGraphId


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FakeNavigator(GraphNavigator):
    """Deterministic fake navigator for testing dispatch logic."""

    def __init__(self, name: str = "keyword_bfs", results: list | None = None):
        self._name = name
        self._results = results or []
        self.call_count = 0

    @property
    def strategy_name(self) -> str:
        return self._name

    async def navigate(self, *, query, wiki_graph, top_n=8):
        self.call_count += 1
        return self._results


@pytest.fixture
def mock_wiki_repo():
    return AsyncMock(spec=WikiGraphRepository)


@pytest.fixture
def fake_navigator():
    return FakeNavigator(
        results=[
            NavigationResult(
                node_id="退貨政策",
                label="退貨政策",
                summary="30 天內可退",
                score=10.0,
                source_doc_id="doc-001",
                path_context="seed (matched: 退貨)",
            ),
            NavigationResult(
                node_id="退款流程",
                label="退款流程",
                summary="",
                score=5.0,
                source_doc_id="doc-002",
                path_context="neighbor",
            ),
        ]
    )


@pytest.fixture
def use_case(mock_wiki_repo, fake_navigator):
    return QueryWikiUseCase(
        wiki_graph_repository=mock_wiki_repo,
        navigators={"keyword_bfs": fake_navigator},
    )


# ============================================================================
# Strategy dispatch
# ============================================================================


def test_dispatch_to_keyword_bfs_navigator(
    use_case, mock_wiki_repo, fake_navigator
):
    mock_wiki_repo.find_by_bot_id.return_value = WikiGraph(
        id=WikiGraphId(value="g-001"),
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="ready",
        nodes={"x": {"label": "x"}},
    )

    result = _run(
        use_case.execute(
            QueryWikiCommand(
                tenant_id="t-001",
                bot_id="b-001",
                query="退貨",
                navigation_strategy="keyword_bfs",
            )
        )
    )

    assert fake_navigator.call_count == 1
    assert len(result.nodes) == 2
    assert result.tool_response["success"] is True


def test_unknown_strategy_raises_validation_error(use_case):
    with pytest.raises(ValidationError) as exc_info:
        _run(
            use_case.execute(
                QueryWikiCommand(
                    tenant_id="t-001",
                    bot_id="b-001",
                    query="x",
                    navigation_strategy="unknown_strategy",
                )
            )
        )
    assert "Unknown wiki navigation strategy" in str(exc_info.value)


def test_strategy_in_valid_list_but_not_registered(mock_wiki_repo):
    """Defensive check: if VALID_NAVIGATION_STRATEGIES says it's valid but
    Container forgot to register a navigator instance, should raise."""
    # navigators dict is empty
    use_case = QueryWikiUseCase(
        wiki_graph_repository=mock_wiki_repo,
        navigators={},
    )
    with pytest.raises(ValidationError) as exc_info:
        _run(
            use_case.execute(
                QueryWikiCommand(
                    tenant_id="t-001",
                    bot_id="b-001",
                    query="x",
                    navigation_strategy="keyword_bfs",  # valid but unregistered
                )
            )
        )
    assert "no navigator instance" in str(exc_info.value).lower()


# ============================================================================
# Wiki graph not compiled / various status states
# ============================================================================


def test_wiki_graph_not_found_returns_readable_error(use_case, mock_wiki_repo):
    mock_wiki_repo.find_by_bot_id.return_value = None

    result = _run(
        use_case.execute(
            QueryWikiCommand(
                tenant_id="t-001",
                bot_id="b-001",
                query="x",
                navigation_strategy="keyword_bfs",
            )
        )
    )

    assert result.nodes == []
    assert result.tool_response["success"] is True
    assert "尚未編譯" in result.tool_response["context"]
    assert result.tool_response["sources"] == []


def test_wiki_graph_compiling_returns_readable_error(
    use_case, mock_wiki_repo
):
    mock_wiki_repo.find_by_bot_id.return_value = WikiGraph(
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="compiling",
    )

    result = _run(
        use_case.execute(
            QueryWikiCommand(
                tenant_id="t-001",
                bot_id="b-001",
                query="x",
                navigation_strategy="keyword_bfs",
            )
        )
    )

    assert "編譯中" in result.tool_response["context"]


def test_wiki_graph_failed_returns_readable_error(use_case, mock_wiki_repo):
    mock_wiki_repo.find_by_bot_id.return_value = WikiGraph(
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="failed",
    )

    result = _run(
        use_case.execute(
            QueryWikiCommand(
                tenant_id="t-001",
                bot_id="b-001",
                query="x",
                navigation_strategy="keyword_bfs",
            )
        )
    )

    assert "編譯失敗" in result.tool_response["context"]


def test_wiki_graph_pending_returns_readable_error(use_case, mock_wiki_repo):
    mock_wiki_repo.find_by_bot_id.return_value = WikiGraph(
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="pending",
    )

    result = _run(
        use_case.execute(
            QueryWikiCommand(
                tenant_id="t-001",
                bot_id="b-001",
                query="x",
                navigation_strategy="keyword_bfs",
            )
        )
    )

    assert "尚未開始編譯" in result.tool_response["context"]


def test_stale_status_still_allows_query(use_case, mock_wiki_repo):
    """status=stale should still be queryable (data potentially outdated)."""
    mock_wiki_repo.find_by_bot_id.return_value = WikiGraph(
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="stale",
        nodes={"x": {"label": "x"}},
    )

    result = _run(
        use_case.execute(
            QueryWikiCommand(
                tenant_id="t-001",
                bot_id="b-001",
                query="x",
                navigation_strategy="keyword_bfs",
            )
        )
    )

    # Navigator was called → stale graphs are queryable
    assert result.tool_response["success"] is True


# ============================================================================
# Sources schema (RAG-compatible)
# ============================================================================


def test_sources_schema_matches_rag_tool_format(
    use_case, mock_wiki_repo, fake_navigator
):
    mock_wiki_repo.find_by_bot_id.return_value = WikiGraph(
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="ready",
        nodes={"x": {"label": "x"}},
    )

    result = _run(
        use_case.execute(
            QueryWikiCommand(
                tenant_id="t-001",
                bot_id="b-001",
                query="退貨",
                navigation_strategy="keyword_bfs",
            )
        )
    )

    sources = result.tool_response["sources"]
    assert len(sources) == 2

    # Each source must match RAG schema:
    # {document_name, content_snippet, score, chunk_id, document_id}
    s = sources[0]
    assert "document_name" in s
    assert "content_snippet" in s
    assert "score" in s
    assert "chunk_id" in s
    assert "document_id" in s
    # content_snippet should combine label + summary
    assert "退貨政策" in s["content_snippet"]
    assert "30 天內可退" in s["content_snippet"]


def test_context_string_joins_results_with_separator(
    use_case, mock_wiki_repo
):
    mock_wiki_repo.find_by_bot_id.return_value = WikiGraph(
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="ready",
        nodes={"x": {"label": "x"}},
    )

    result = _run(
        use_case.execute(
            QueryWikiCommand(
                tenant_id="t-001",
                bot_id="b-001",
                query="退貨",
                navigation_strategy="keyword_bfs",
            )
        )
    )

    context = result.tool_response["context"]
    assert "退貨政策" in context
    assert "退款流程" in context
    assert "\n---\n" in context


def test_navigator_returns_empty_yields_empty_sources(
    mock_wiki_repo,
):
    """If navigator finds nothing, return empty sources without crashing."""
    empty_navigator = FakeNavigator(results=[])
    use_case = QueryWikiUseCase(
        wiki_graph_repository=mock_wiki_repo,
        navigators={"keyword_bfs": empty_navigator},
    )
    mock_wiki_repo.find_by_bot_id.return_value = WikiGraph(
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        status="ready",
        nodes={"x": {"label": "x"}},
    )

    result = _run(
        use_case.execute(
            QueryWikiCommand(
                tenant_id="t-001",
                bot_id="b-001",
                query="無關",
                navigation_strategy="keyword_bfs",
            )
        )
    )

    assert result.nodes == []
    assert result.tool_response["sources"] == []
    assert result.tool_response["context"] == ""
