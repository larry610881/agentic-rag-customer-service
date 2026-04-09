"""LLMWikiCompilerService unit tests — mock LLMService.

驗證：
- JSON 解析（純 JSON / fenced code block / 有前綴雜訊）
- 錯誤容錯（LLM throw / 無效 JSON）
- 空文件跳過
- 節點去重、ID 產生
- confidence / score 正規化
- 文件長度截斷

注意：專案使用 `-p no:asyncio`，pytest.mark.asyncio 無效。
改用 `_run()` 同步包裝 async 呼叫（與 pytest-bdd step 相同 pattern）。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.rag.value_objects import LLMResult, TokenUsage
from src.infrastructure.wiki.llm_wiki_compiler import LLMWikiCompilerService


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_usage(**kwargs) -> TokenUsage:
    return TokenUsage(
        model=kwargs.get("model", "test-model"),
        input_tokens=kwargs.get("input_tokens", 100),
        output_tokens=kwargs.get("output_tokens", 50),
        total_tokens=kwargs.get("total_tokens", 150),
        estimated_cost=kwargs.get("estimated_cost", 0.001),
    )


def _make_llm_result(text: str, **usage_kwargs) -> LLMResult:
    return LLMResult(text=text, usage=_make_usage(**usage_kwargs))


def _make_mock_llm(response_text: str | Exception) -> MagicMock:
    mock = MagicMock()
    if isinstance(response_text, Exception):
        mock.generate = AsyncMock(side_effect=response_text)
    else:
        mock.generate = AsyncMock(return_value=_make_llm_result(response_text))
    return mock


@pytest.fixture
def compiler_factory():
    def _factory(llm_mock):
        return LLMWikiCompilerService(llm_service=llm_mock)

    return _factory


# ============================================================================
# JSON parsing
# ============================================================================


def test_pure_json_response(compiler_factory):
    mock = _make_mock_llm(
        '{"nodes":[{"id":"退貨","label":"退貨政策","type":"policy"}],"edges":[]}'
    )
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="文件內容"))
    assert len(result.nodes) == 1
    assert result.nodes[0].label == "退貨政策"
    assert result.nodes[0].type == "policy"
    assert result.nodes[0].source_doc_id == "doc-1"
    assert result.usage is not None


def test_fenced_code_block(compiler_factory):
    text = (
        "```json\n"
        '{"nodes":[{"id":"n1","label":"測試"}],"edges":[]}\n'
        "```"
    )
    mock = _make_mock_llm(text)
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert len(result.nodes) == 1
    assert result.nodes[0].label == "測試"


def test_leading_preamble_tolerated(compiler_factory):
    text = (
        "Here is the JSON:\n"
        '{"nodes":[{"id":"n1","label":"A"}],"edges":[]}'
    )
    mock = _make_mock_llm(text)
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert len(result.nodes) == 1


def test_invalid_json_returns_empty(compiler_factory):
    mock = _make_mock_llm("not json at all")
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert result.nodes == ()
    assert result.edges == ()
    # Usage still tracked even though parse failed
    assert result.usage is not None


def test_llm_exception_returns_empty(compiler_factory):
    mock = _make_mock_llm(RuntimeError("LLM timeout"))
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert result.nodes == ()
    assert result.edges == ()
    assert result.usage is None  # LLM never returned


# ============================================================================
# Empty content handling
# ============================================================================


def test_empty_string_skipped(compiler_factory):
    mock = _make_mock_llm('{"nodes":[],"edges":[]}')
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content=""))
    assert result.nodes == ()
    mock.generate.assert_not_called()


def test_whitespace_only_skipped(compiler_factory):
    mock = _make_mock_llm('{"nodes":[],"edges":[]}')
    compiler = compiler_factory(mock)
    result = _run(
        compiler.extract(document_id="doc-1", content="   \n\n  ")
    )
    assert result.nodes == ()
    mock.generate.assert_not_called()


# ============================================================================
# Node building
# ============================================================================


def test_auto_generates_id_from_label_when_missing(compiler_factory):
    mock = _make_mock_llm('{"nodes":[{"label":"退貨政策"}],"edges":[]}')
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert len(result.nodes) == 1
    assert result.nodes[0].id != ""


def test_drops_nodes_without_label(compiler_factory):
    mock = _make_mock_llm(
        '{"nodes":[{"id":"n1","label":""},{"id":"n2","label":"OK"}],'
        '"edges":[]}'
    )
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert len(result.nodes) == 1
    assert result.nodes[0].label == "OK"


def test_default_type_is_concept(compiler_factory):
    mock = _make_mock_llm('{"nodes":[{"id":"n1","label":"test"}],"edges":[]}')
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert result.nodes[0].type == "concept"


def test_duplicate_ids_get_unique_suffix(compiler_factory):
    mock = _make_mock_llm(
        '{"nodes":[{"id":"same","label":"A"},{"id":"same","label":"B"}],'
        '"edges":[]}'
    )
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert len(result.nodes) == 2
    assert result.nodes[0].id != result.nodes[1].id


# ============================================================================
# Edge building
# ============================================================================


def test_valid_edge(compiler_factory):
    mock = _make_mock_llm(
        '{"nodes":[],"edges":[{"source":"a","target":"b","relation":"requires",'
        '"confidence":"EXTRACTED","confidence_score":1.0}]}'
    )
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert len(result.edges) == 1
    assert result.edges[0].source == "a"
    assert result.edges[0].target == "b"
    assert result.edges[0].relation == "requires"
    assert result.edges[0].confidence == "EXTRACTED"


def test_extracted_edge_forced_to_score_1(compiler_factory):
    """EXTRACTED confidence should always have score 1.0 even if LLM returns other."""
    mock = _make_mock_llm(
        '{"nodes":[],"edges":[{"source":"a","target":"b","relation":"r",'
        '"confidence":"EXTRACTED","confidence_score":0.5}]}'
    )
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert result.edges[0].confidence_score == 1.0


def test_invalid_confidence_becomes_inferred(compiler_factory):
    mock = _make_mock_llm(
        '{"nodes":[],"edges":[{"source":"a","target":"b","relation":"r",'
        '"confidence":"WEIRD"}]}'
    )
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert result.edges[0].confidence == "INFERRED"


def test_drops_edges_missing_required_fields(compiler_factory):
    mock = _make_mock_llm(
        '{"nodes":[],"edges":['
        '{"source":"a","target":"b"},'  # missing relation
        '{"source":"c","relation":"r"},'  # missing target
        '{"source":"d","target":"e","relation":"valid"}'
        "]}"
    )
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert len(result.edges) == 1
    assert result.edges[0].relation == "valid"


def test_score_clamped_to_01(compiler_factory):
    mock = _make_mock_llm(
        '{"nodes":[],"edges":['
        '{"source":"a","target":"b","relation":"r","confidence":"INFERRED","confidence_score":2.5},'
        '{"source":"c","target":"d","relation":"r","confidence":"INFERRED","confidence_score":-1.0}'
        "]}"
    )
    compiler = compiler_factory(mock)
    result = _run(compiler.extract(document_id="doc-1", content="x"))
    assert result.edges[0].confidence_score == 1.0
    assert result.edges[1].confidence_score == 0.0


# ============================================================================
# Content truncation
# ============================================================================


def test_long_content_truncated(compiler_factory):
    mock = _make_mock_llm('{"nodes":[],"edges":[]}')
    compiler = LLMWikiCompilerService(llm_service=mock, max_content_chars=100)
    long_content = "a" * 500
    _run(compiler.extract(document_id="doc-1", content=long_content))
    # LLM received truncated content
    call_kwargs = mock.generate.await_args.kwargs
    user_message = call_kwargs["user_message"]
    # User message = prompt template + truncated content (100 chars)
    # The original 500-char content should NOT fit
    assert user_message.count("a") <= 100
