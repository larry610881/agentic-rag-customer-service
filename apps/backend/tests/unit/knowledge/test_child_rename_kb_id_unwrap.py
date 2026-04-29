"""Regression test for hotfix 632d6e2 (4/28 KnowledgeBaseId VO unwrap bug).

當 PDF 子頁 LLM rename 完成寫 token_usage_records 時，kb_id 欄位是 VARCHAR：
- 之前：直接傳 kb.id (KnowledgeBaseId VO) → asyncpg DataError $12
- 修法：unwrap 成 .value 字串

此檔保證未來再回歸時測試會 fail。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.application.knowledge._child_rename import rename_child_page_if_pdf
from src.domain.knowledge.value_objects import KnowledgeBaseId


def _run(coro):
    # fresh event loop 避免 BDD 測試 pollution（同其他 unit test 修法）
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_kb_with_vo(kb_id_str: str = "kb-uuid-12345"):
    """模擬 prod kb 物件 — id 是 KnowledgeBaseId VO（dataclass with .value）。"""
    return SimpleNamespace(
        id=KnowledgeBaseId(value=kb_id_str),
        context_model="anthropic:claude-haiku-4-5",
    )


def _make_kb_with_str(kb_id_str: str = "kb-uuid-12345"):
    """模擬 test fixture kb 物件 — id 直接是 str（不 wrap VO）。"""
    return SimpleNamespace(
        id=kb_id_str,
        context_model="anthropic:claude-haiku-4-5",
    )


def test_rename_passes_str_kb_id_to_record_usage_when_kb_id_is_VO():
    """關鍵 regression：kb.id 是 VO 時，record_usage.execute 收到 .value (str)。"""
    kb = _make_kb_with_vo("kb-real-uuid-abc")
    record_usage = AsyncMock()
    log = SimpleNamespace(
        info=lambda *a, **kw: None,
        warning=lambda *a, **kw: None,
    )

    # mock call_llm 回傳一個合法 result
    fake_result = SimpleNamespace(
        text="第 1 頁 — 主題", input_tokens=100, output_tokens=20
    )
    with patch(
        "src.infrastructure.llm.llm_caller.call_llm",
        new_callable=AsyncMock,
        return_value=fake_result,
    ), patch(
        "src.infrastructure.db.engine.async_session_factory"
    ) as mock_session_factory:
        # mock session 給最終 update filename SQL（不真執行）
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = (
            mock_session
        )
        _run(
            rename_child_page_if_pdf(
                document_id="doc-1",
                page_number=1,
                content="some PDF content here",
                kb=kb,
                tenant_id="t-1",
                doc_repo=AsyncMock(),
                tenant_repo=None,
                record_usage=record_usage,
                context_service=None,
                log=log,
            )
        )

    # ✅ record_usage.execute 應收到 str 不是 VO
    assert record_usage.execute.await_count == 1
    call_kwargs = record_usage.execute.await_args.kwargs
    assert call_kwargs["kb_id"] == "kb-real-uuid-abc"
    assert isinstance(call_kwargs["kb_id"], str)
    # ❌ 絕不應是 VO
    assert not isinstance(call_kwargs["kb_id"], KnowledgeBaseId)


def test_rename_handles_str_kb_id_directly_no_AttributeError():
    """test fixture 給 str kb.id 時也要 work（不能用 .value 強制取屬性炸）。"""
    kb = _make_kb_with_str("kb-str-id")
    record_usage = AsyncMock()
    log = SimpleNamespace(
        info=lambda *a, **kw: None,
        warning=lambda *a, **kw: None,
    )

    fake_result = SimpleNamespace(
        text="第 2 頁 — 主題", input_tokens=50, output_tokens=10
    )
    with patch(
        "src.infrastructure.llm.llm_caller.call_llm",
        new_callable=AsyncMock,
        return_value=fake_result,
    ), patch(
        "src.infrastructure.db.engine.async_session_factory"
    ) as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = (
            mock_session
        )
        _run(
            rename_child_page_if_pdf(
                document_id="doc-2",
                page_number=2,
                content="content",
                kb=kb,
                tenant_id="t-1",
                doc_repo=AsyncMock(),
                tenant_repo=None,
                record_usage=record_usage,
                context_service=None,
                log=log,
            )
        )

    # str kb_id 也應正確傳遞（hasattr(_, "value") False 走原樣）
    assert record_usage.execute.await_count == 1
    assert record_usage.execute.await_args.kwargs["kb_id"] == "kb-str-id"


def test_rename_skips_record_usage_when_kb_is_None():
    """kb=None 時（極端 edge case）應 silent skip 不炸。"""
    record_usage = AsyncMock()
    log = SimpleNamespace(
        info=lambda *a, **kw: None,
        warning=lambda *a, **kw: None,
    )
    # kb=None → model 解析後為空 → 直接 return，rename 不執行
    _run(
        rename_child_page_if_pdf(
            document_id="doc-x",
            page_number=1,
            content="content",
            kb=None,
            tenant_id="t-1",
            doc_repo=AsyncMock(),
            tenant_repo=None,
            record_usage=record_usage,
            context_service=None,
            log=log,
        )
    )
    # 沒呼叫到 record_usage（model 為空就 return 了）
    record_usage.execute.assert_not_called()


def test_rename_skips_when_content_empty():
    """content 空字串 → 立刻 return 不做任何事。"""
    record_usage = AsyncMock()
    log = SimpleNamespace(
        info=lambda *a, **kw: None,
        warning=lambda *a, **kw: None,
    )
    _run(
        rename_child_page_if_pdf(
            document_id="doc-x",
            page_number=1,
            content="",
            kb=_make_kb_with_vo(),
            tenant_id="t-1",
            doc_repo=AsyncMock(),
            tenant_repo=None,
            record_usage=record_usage,
            context_service=None,
            log=log,
        )
    )
    record_usage.execute.assert_not_called()
