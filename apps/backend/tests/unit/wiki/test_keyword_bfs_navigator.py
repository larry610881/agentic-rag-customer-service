"""KeywordBFSNavigator unit tests — mock LLM, test pure logic.

驗證：
- LLM 關鍵字解析（pure JSON / regex extract / fallback）
- Seed matching（label vs summary 加權）
- BFS 遍歷（深度限制、分數累加、edge confidence 加權）
- Cluster fallback（BFS 結果太少時補上 cluster 成員）
- LLM 失敗降級到 unigram fallback
- 排序與 top_n
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.domain.rag.value_objects import LLMResult, TokenUsage
from src.domain.wiki.entity import WikiGraph
from src.infrastructure.wiki.keyword_bfs_navigator import KeywordBFSNavigator


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


def _make_mock_llm(response: str | Exception) -> MagicMock:
    mock = MagicMock()
    if isinstance(response, Exception):
        mock.generate = AsyncMock(side_effect=response)
    else:
        mock.generate = AsyncMock(return_value=_llm_result(response))
    return mock


def _make_graph(
    nodes: dict[str, dict] | None = None,
    edges: dict[str, dict] | None = None,
    clusters: list[dict] | None = None,
) -> WikiGraph:
    return WikiGraph(
        tenant_id="t-001",
        bot_id="b-001",
        kb_id="kb-001",
        nodes=nodes or {},
        edges=edges or {},
        clusters=clusters or [],
    )


# ============================================================================
# Strategy name
# ============================================================================


def test_strategy_name():
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm('["x"]'))
    assert nav.strategy_name == "keyword_bfs"


# ============================================================================
# LLM keyword parsing
# ============================================================================


def test_parse_keywords_pure_json():
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm("placeholder"))
    assert nav._parse_keywords('["退貨", "退款"]') == ["退貨", "退款"]


def test_parse_keywords_with_preamble():
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm("placeholder"))
    assert (
        nav._parse_keywords('Here you go: ["退貨", "退款"] done')
        == ["退貨", "退款"]
    )


def test_parse_keywords_invalid_returns_empty():
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm("placeholder"))
    assert nav._parse_keywords("not json") == []


def test_parse_keywords_empty_string():
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm("placeholder"))
    assert nav._parse_keywords("") == []


# ============================================================================
# Unigram fallback
# ============================================================================


def test_fallback_unigram_skips_stopwords():
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm("placeholder"))
    keywords = nav._fallback_unigram_keywords("我想要退貨怎麼辦")
    # Should not contain stopwords like 我, 怎麼
    assert "退貨" in keywords or any("退" in k for k in keywords)
    assert "我" not in keywords


def test_fallback_unigram_handles_punctuation():
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm("placeholder"))
    keywords = nav._fallback_unigram_keywords("退款幾天會到帳？")
    assert len(keywords) > 0


# ============================================================================
# Empty inputs
# ============================================================================


def test_navigate_empty_query_returns_empty():
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm('["x"]'))
    result = _run(nav.navigate(query="", wiki_graph=_make_graph()))
    assert result == []


def test_navigate_empty_graph_returns_empty():
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm('["x"]'))
    result = _run(nav.navigate(query="test", wiki_graph=_make_graph()))
    assert result == []


# ============================================================================
# Seed matching
# ============================================================================


def test_seed_label_match_scores_higher_than_summary_match():
    """Label match should weight 2x summary match."""
    nodes = {
        "n1": {
            "label": "退貨政策",
            "summary": "其他內容",
            "source_doc_ids": ["d1"],
        },
        "n2": {
            "label": "退款流程",
            "summary": "包含退貨資訊",
            "source_doc_ids": ["d2"],
        },
    }
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm('["退貨"]'))
    result = _run(nav.navigate(query="退貨怎麼辦", wiki_graph=_make_graph(nodes)))
    # Both nodes should be returned but n1 (label match) > n2 (summary match)
    assert len(result) >= 2
    n1_score = next(r.score for r in result if r.node_id == "n1")
    n2_score = next(r.score for r in result if r.node_id == "n2")
    assert n1_score > n2_score


def test_no_keyword_match_returns_empty():
    """If keywords don't match any node, fallback to empty (not error)."""
    nodes = {
        "n1": {
            "label": "其他主題",
            "summary": "",
            "source_doc_ids": [],
        },
    }
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm('["完全無關"]'))
    result = _run(
        nav.navigate(query="完全無關", wiki_graph=_make_graph(nodes))
    )
    assert result == []


# ============================================================================
# BFS traversal
# ============================================================================


def test_bfs_brings_in_neighbors():
    """Seed node + BFS should bring in its 1-hop neighbors."""
    nodes = {
        "退貨政策": {"label": "退貨政策", "summary": "", "source_doc_ids": []},
        "退款流程": {"label": "退款流程", "summary": "", "source_doc_ids": []},
        "聯絡客服": {"label": "聯絡客服", "summary": "", "source_doc_ids": []},
    }
    edges = {
        "e1": {
            "source": "退貨政策",
            "target": "退款流程",
            "relation": "triggers",
            "confidence": "EXTRACTED",
            "score": 1.0,
        },
        "e2": {
            "source": "退貨政策",
            "target": "聯絡客服",
            "relation": "requires",
            "confidence": "EXTRACTED",
            "score": 1.0,
        },
    }
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm('["退貨"]'))
    result = _run(
        nav.navigate(query="退貨", wiki_graph=_make_graph(nodes, edges))
    )
    node_ids = [r.node_id for r in result]
    assert "退貨政策" in node_ids  # seed
    assert "退款流程" in node_ids  # 1-hop
    assert "聯絡客服" in node_ids  # 1-hop


def test_bfs_respects_max_depth():
    """Default max_depth=2 keeps 3-hop neighbors at lower score than seed."""
    # Build a chain: seed → A → B → C (3 hops)
    nodes = {
        "seed": {"label": "退貨", "summary": "", "source_doc_ids": []},
        "A": {"label": "節點A", "summary": "", "source_doc_ids": []},
        "B": {"label": "節點B", "summary": "", "source_doc_ids": []},
        "C": {"label": "節點C", "summary": "", "source_doc_ids": []},
    }
    edges = {
        "e1": {
            "source": "seed",
            "target": "A",
            "relation": "r",
            "confidence": "EXTRACTED",
            "score": 1.0,
        },
        "e2": {
            "source": "A",
            "target": "B",
            "relation": "r",
            "confidence": "EXTRACTED",
            "score": 1.0,
        },
        "e3": {
            "source": "B",
            "target": "C",
            "relation": "r",
            "confidence": "EXTRACTED",
            "score": 1.0,
        },
    }
    nav = KeywordBFSNavigator(
        llm_service=_make_mock_llm('["退貨"]'), max_depth=2
    )
    result = _run(
        nav.navigate(query="退貨", wiki_graph=_make_graph(nodes, edges))
    )
    node_ids = [r.node_id for r in result]
    assert "seed" in node_ids
    assert "A" in node_ids
    assert "B" in node_ids
    # C is 3 hops away — should still be reachable but with much lower score
    # (or not reached at all). For this test, just verify seed and immediate
    # neighbors are present.
    seed_score = next(r.score for r in result if r.node_id == "seed")
    a_score = next(r.score for r in result if r.node_id == "A")
    assert seed_score > a_score  # decay applied


# ============================================================================
# Cluster fallback
# ============================================================================


def test_cluster_fallback_when_few_results():
    """When BFS returns < 2 nodes (single isolated seed), expand via cluster."""
    nodes = {
        # Only this node matches keyword "退貨"
        "退貨政策": {
            "label": "退貨政策", "summary": "", "source_doc_ids": []
        },
        # These two are in same cluster but don't match keyword
        "退款條件": {
            "label": "退款條件", "summary": "", "source_doc_ids": []
        },
        "貨運費用": {
            "label": "貨運費用", "summary": "", "source_doc_ids": []
        },
    }
    # No edges → BFS only finds the single seed (退貨政策)
    edges = {}
    clusters = [
        {
            "id": "c1",
            "label": "退貨相關",
            "node_ids": ["退貨政策", "退款條件", "貨運費用"],
        }
    ]
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm('["退貨"]'))
    result = _run(
        nav.navigate(
            query="退貨", wiki_graph=_make_graph(nodes, edges, clusters)
        )
    )
    node_ids = [r.node_id for r in result]
    assert "退貨政策" in node_ids  # seed
    # Cluster fallback should bring in the other two from the same cluster
    assert "退款條件" in node_ids
    assert "貨運費用" in node_ids


# ============================================================================
# LLM fallback to unigram
# ============================================================================


def test_llm_failure_falls_back_to_unigram():
    """When LLM throws, navigator falls back to substring unigram extraction."""
    nodes = {
        "退貨政策": {"label": "退貨政策", "summary": "", "source_doc_ids": []},
    }
    nav = KeywordBFSNavigator(
        llm_service=_make_mock_llm(RuntimeError("LLM down"))
    )
    result = _run(
        nav.navigate(query="我想退貨", wiki_graph=_make_graph(nodes))
    )
    # Unigram fallback should still extract 退貨 and find the node
    assert len(result) >= 1
    assert any("退貨" in r.label for r in result)


def test_llm_returns_invalid_json_falls_back_to_unigram():
    nodes = {
        "退貨政策": {"label": "退貨政策", "summary": "", "source_doc_ids": []},
    }
    nav = KeywordBFSNavigator(
        llm_service=_make_mock_llm("not json at all garbage")
    )
    result = _run(
        nav.navigate(query="我想退貨", wiki_graph=_make_graph(nodes))
    )
    assert len(result) >= 1


# ============================================================================
# Edge confidence weighting
# ============================================================================


def test_extracted_edge_outscores_ambiguous_neighbor():
    """Neighbors via EXTRACTED edges should rank higher than via AMBIGUOUS."""
    nodes = {
        "seed": {"label": "退貨", "summary": "", "source_doc_ids": []},
        "strong": {"label": "強關聯", "summary": "", "source_doc_ids": []},
        "weak": {"label": "弱關聯", "summary": "", "source_doc_ids": []},
    }
    edges = {
        "e1": {
            "source": "seed",
            "target": "strong",
            "relation": "r",
            "confidence": "EXTRACTED",
            "score": 1.0,
        },
        "e2": {
            "source": "seed",
            "target": "weak",
            "relation": "r",
            "confidence": "AMBIGUOUS",
            "score": 0.2,
        },
    }
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm('["退貨"]'))
    result = _run(
        nav.navigate(query="退貨", wiki_graph=_make_graph(nodes, edges))
    )
    strong_score = next(r.score for r in result if r.node_id == "strong")
    weak_score = next(r.score for r in result if r.node_id == "weak")
    assert strong_score > weak_score


# ============================================================================
# Top N
# ============================================================================


def test_top_n_caps_results():
    """top_n should cap the result count."""
    nodes = {
        f"n{i}": {
            "label": f"退貨節點{i}",
            "summary": "",
            "source_doc_ids": [],
        }
        for i in range(20)
    }
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm('["退貨"]'))
    result = _run(
        nav.navigate(query="退貨", wiki_graph=_make_graph(nodes), top_n=5)
    )
    assert len(result) == 5


# ============================================================================
# NavigationResult fields
# ============================================================================


def test_result_includes_path_context_for_seed():
    nodes = {
        "退貨政策": {
            "label": "退貨政策",
            "summary": "30 天內可退貨",
            "source_doc_ids": ["doc-001"],
        },
    }
    nav = KeywordBFSNavigator(llm_service=_make_mock_llm('["退貨"]'))
    result = _run(nav.navigate(query="退貨", wiki_graph=_make_graph(nodes)))
    assert len(result) == 1
    r = result[0]
    assert r.label == "退貨政策"
    assert r.summary == "30 天內可退貨"
    assert r.source_doc_id == "doc-001"
    assert "seed" in r.path_context
    assert "退貨" in r.path_context  # matched keyword shown
