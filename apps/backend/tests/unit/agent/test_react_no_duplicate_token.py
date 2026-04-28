"""Regression test — ReAct streaming 不該重複 emit 同一段文字

Bug history (2026-04-28):
b50cbc1 修了 fallback path 的 list[dict] content 處理時，把「messages mode
已經 stream 過就 skip fallback」這個保護拿掉了 → updates mode 補吐一次完整
內容 → 前端對話泡泡看到回答出現兩遍。

此測試守住：當 _handle_text_chunk 已經 emit token 事件後，updates mode
看到同一條 AIMessage 不該再吐一次。
"""

from src.infrastructure.langgraph.react_agent_service import ReActAgentService


def test_handle_text_chunk_sets_llm_generating_emitted_for_str_content():
    """messages mode 第一個 chunk 進來，應 emit llm_generating + token，
    並把 llm_generating_emitted 設為 True 防止 fallback 再 emit。"""
    from langchain_core.messages import AIMessageChunk

    chunk = AIMessageChunk(content="嗨")
    events, emitted = ReActAgentService._handle_text_chunk(
        chunk,
        metadata={"langgraph_node": "agent"},
        llm_generating_emitted=False,
    )
    assert emitted is True  # 之後 fallback 看到此 flag 應 skip
    assert any(e["type"] == "token" and e["content"] == "嗨" for e in events)


def test_handle_text_chunk_sets_llm_generating_emitted_for_list_content():
    """Anthropic 直連 list[dict] 也該設 flag — 否則 messages mode 串完後
    fallback 會把整段內容再吐一次。"""
    from langchain_core.messages import AIMessageChunk

    chunk = AIMessageChunk(
        content=[
            {"type": "text", "text": "嗨", "index": 0},
        ]
    )
    events, emitted = ReActAgentService._handle_text_chunk(
        chunk,
        metadata={"langgraph_node": "agent"},
        llm_generating_emitted=False,
    )
    assert emitted is True
    assert any(e["type"] == "token" and e["content"] == "嗨" for e in events)


def test_subsequent_chunks_keep_emitted_flag_true():
    """連續多個 chunks 都應保持 llm_generating_emitted=True，
    讓 updates mode 整路 skip fallback。"""
    from langchain_core.messages import AIMessageChunk

    # 第一個 chunk → 設 flag True
    chunk1 = AIMessageChunk(content="嗨")
    _, emitted = ReActAgentService._handle_text_chunk(
        chunk1,
        metadata={"langgraph_node": "agent"},
        llm_generating_emitted=False,
    )
    assert emitted is True

    # 第二個 chunk → flag 應仍為 True（不 reset）
    chunk2 = AIMessageChunk(content="，")
    events2, emitted2 = ReActAgentService._handle_text_chunk(
        chunk2,
        metadata={"langgraph_node": "agent"},
        llm_generating_emitted=emitted,
    )
    assert emitted2 is True
    # 後續 chunk 不該重複 emit llm_generating status（只在第一個 chunk 才 emit）
    statuses = [e for e in events2 if e["type"] == "status"]
    assert len(statuses) == 0
    # 但仍要 emit token
    assert any(e["type"] == "token" for e in events2)
