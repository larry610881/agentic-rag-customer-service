"""Regression test — ReAct streaming chunk content 格式相容性

Bug history（2026-04-27）:
litellm:azure_ai/claude-haiku-4-5 切換到 anthropic:claude-haiku-4-5 後，
ChatAnthropic 直連的 AIMessageChunk.content 是 list[dict]
（[{"type":"text","text":"...","index":0}]），原本程式 str(content) 直接吃
Python repr，前端看到 [{'text':'...', 'type':'text', 'index':0}] 而非純文字。

此測試守住「content 為 list 時要正確抽出文字」的合約。
"""
from langchain_core.messages import AIMessageChunk

from src.infrastructure.langgraph.react_agent_service import ReActAgentService


def _call(chunk: AIMessageChunk):
    return ReActAgentService._handle_text_chunk(
        chunk,
        metadata={"langgraph_node": "agent"},
        llm_generating_emitted=False,
    )


def test_str_content_passes_through():
    """OpenAI / LiteLLM compat — content 是純字串"""
    chunk = AIMessageChunk(content="hello world")
    events, emitted = _call(chunk)
    assert emitted is True
    assert {"type": "token", "content": "hello world"} in events


def test_list_content_extracts_text_blocks():
    """Anthropic 直連 — content 是 list of {type, text, index}"""
    chunk = AIMessageChunk(
        content=[
            {"type": "text", "text": "我只", "index": 0},
            {"type": "text", "text": "能協助", "index": 0},
        ]
    )
    events, emitted = _call(chunk)
    assert emitted is True
    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) == 1
    assert token_events[0]["content"] == "我只能協助"


def test_list_content_skips_non_text_blocks():
    """Anthropic content list 中可能混入 tool_use 等非 text block — 不應出現在輸出"""
    chunk = AIMessageChunk(
        content=[
            {"type": "text", "text": "hello", "index": 0},
            {"type": "tool_use", "id": "x", "name": "y", "input": {}},
        ]
    )
    events, _ = _call(chunk)
    token_events = [e for e in events if e["type"] == "token"]
    assert token_events[0]["content"] == "hello"


def test_empty_list_emits_no_token():
    """純空 list（initial chunk 無內容）不應 emit token / status"""
    chunk = AIMessageChunk(content=[])
    events, emitted = _call(chunk)
    assert emitted is False
    assert events == []


def test_empty_str_emits_no_token():
    """純空字串同樣不 emit"""
    chunk = AIMessageChunk(content="")
    events, emitted = _call(chunk)
    assert emitted is False
    assert events == []


def test_list_with_only_empty_text_emits_no_token():
    """list 中所有 text 都空也不 emit"""
    chunk = AIMessageChunk(content=[{"type": "text", "text": "", "index": 0}])
    events, emitted = _call(chunk)
    assert emitted is False
    assert events == []


def test_non_agent_node_returns_empty():
    """非 agent node 的 chunk 應原封不動 ignore"""
    chunk = AIMessageChunk(content="should be ignored")
    events, emitted = ReActAgentService._handle_text_chunk(
        chunk,
        metadata={"langgraph_node": "tools"},
        llm_generating_emitted=False,
    )
    assert events == []
    assert emitted is False
