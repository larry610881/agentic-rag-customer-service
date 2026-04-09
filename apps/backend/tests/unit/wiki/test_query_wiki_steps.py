"""Wiki Query BDD Step Definitions — full unit-level test of the query flow.

Uses real KeywordBFSNavigator + real QueryWikiUseCase + mocked LLMService and
mocked WikiGraphRepository. This integrates use case + navigator + tool format
all in one BDD scenario.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.wiki.query_wiki_use_case import (
    QueryWikiCommand,
    QueryWikiUseCase,
)
from src.domain.rag.value_objects import LLMResult, TokenUsage
from src.domain.wiki.entity import WikiGraph
from src.domain.wiki.repository import WikiGraphRepository
from src.infrastructure.wiki.keyword_bfs_navigator import KeywordBFSNavigator

scenarios("unit/wiki/query_wiki.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _llm_result(text: str) -> LLMResult:
    return LLMResult(
        text=text,
        usage=TokenUsage(
            model="test",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            estimated_cost=0.0001,
        ),
    )


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def mock_wiki_repo():
    return AsyncMock(spec=WikiGraphRepository)


@pytest.fixture
def navigator(mock_llm):
    return KeywordBFSNavigator(llm_service=mock_llm)


@pytest.fixture
def use_case(mock_wiki_repo, navigator):
    return QueryWikiUseCase(
        wiki_graph_repository=mock_wiki_repo,
        navigators={"keyword_bfs": navigator},
    )


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given(parsers.parse('租戶 "{tenant_id}" 存在'))
def tenant_exists(context, tenant_id):
    context["tenant_id"] = tenant_id


@given(parsers.parse('該租戶有 Bot "{bot_id}" 知識模式為 "{mode}"'))
def bot_with_mode(context, bot_id, mode):
    context["bot_id"] = bot_id
    context["knowledge_mode"] = mode


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(
    parsers.parse(
        'Bot "{bot_id}" 已編譯完成的 WikiGraph 包含「{label1}」「{label2}」節點'
    )
)
def graph_with_two_nodes(context, mock_wiki_repo, bot_id, label1, label2):
    graph = WikiGraph(
        tenant_id=context["tenant_id"],
        bot_id=bot_id,
        kb_id="kb-001",
        status="ready",
        nodes={
            label1: {
                "label": label1,
                "summary": "",
                "type": "policy",
                "source_doc_ids": ["doc-001"],
            },
            label2: {
                "label": label2,
                "summary": "",
                "type": "process",
                "source_doc_ids": ["doc-002"],
            },
        },
        edges={
            "e1": {
                "source": label1,
                "target": label2,
                "relation": "triggers",
                "confidence": "EXTRACTED",
                "score": 1.0,
            },
        },
    )
    mock_wiki_repo.find_by_bot_id = AsyncMock(return_value=graph)


@given(
    parsers.parse('Bot "{bot_id}" 已編譯完成的 WikiGraph 包含「{label}」節點')
)
def graph_with_single_node(context, mock_wiki_repo, bot_id, label):
    graph = WikiGraph(
        tenant_id=context["tenant_id"],
        bot_id=bot_id,
        kb_id="kb-001",
        status="ready",
        nodes={
            label: {
                "label": label,
                "summary": "",
                "type": "policy",
                "source_doc_ids": ["doc-001"],
            },
        },
    )
    mock_wiki_repo.find_by_bot_id = AsyncMock(return_value=graph)


@given(parsers.parse('navigation strategy 設定為 "{strategy}"'))
def set_strategy(context, strategy):
    context["strategy"] = strategy


@given(parsers.parse('LLM 關鍵字抽取會回傳 "{keyword}"'))
def llm_returns_keyword(mock_llm, keyword):
    mock_llm.generate = AsyncMock(
        return_value=_llm_result(f'["{keyword}"]')
    )


@given("LLM 關鍵字抽取會拋出例外")
def llm_throws(mock_llm):
    mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))


@given(parsers.parse('Bot "{bot_id}" 沒有編譯過的 WikiGraph'))
def no_wiki_graph(mock_wiki_repo, bot_id):
    mock_wiki_repo.find_by_bot_id = AsyncMock(return_value=None)


@given(parsers.parse('Bot "{bot_id}" 的 WikiGraph status 為 "{status}"'))
def graph_with_status(context, mock_wiki_repo, bot_id, status):
    graph = WikiGraph(
        tenant_id=context["tenant_id"],
        bot_id=bot_id,
        kb_id="kb-001",
        status=status,
    )
    mock_wiki_repo.find_by_bot_id = AsyncMock(return_value=graph)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(parsers.parse('使用者查詢 "{query}"'), target_fixture="result")
def execute_query(context, use_case, query):
    cmd = QueryWikiCommand(
        tenant_id=context["tenant_id"],
        bot_id=context["bot_id"],
        query=query,
        navigation_strategy=context.get("strategy", "keyword_bfs"),
    )
    result = _run(use_case.execute(cmd))
    context["result"] = result
    return result


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then("查詢應成功")
def query_succeeded(result):
    assert result.tool_response["success"] is True


@then(parsers.parse("回傳 sources 應包含「{label}」節點"))
def sources_contain_label(result, label):
    snippets = [s["content_snippet"] for s in result.tool_response["sources"]]
    assert any(label in snippet for snippet in snippets)


@then("回傳 sources 應遵守 RAG tool schema")
def sources_match_rag_schema(result):
    sources = result.tool_response["sources"]
    assert len(sources) > 0
    required_keys = {
        "document_name",
        "content_snippet",
        "score",
        "chunk_id",
        "document_id",
    }
    for s in sources:
        assert required_keys.issubset(s.keys()), (
            f"Missing keys: {required_keys - set(s.keys())}"
        )


@then(parsers.parse("回傳 context 應包含「{text}」提示"))
def context_contains_text(result, text):
    assert text in result.tool_response["context"]


@then("回傳 sources 應為空陣列")
def sources_empty(result):
    assert result.tool_response["sources"] == []


@then(parsers.parse("回傳 sources 應至少包含 {n:d} 個節點"))
def sources_at_least_n(result, n):
    assert len(result.tool_response["sources"]) >= n
