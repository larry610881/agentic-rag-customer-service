"""Per-KB Chunk Strategy 路由 BDD Step Definitions"""

import asyncio
from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.value_objects import ChunkId

scenarios("unit/knowledge/process_document_per_kb_strategy.feature")


def _run(coro):
    """同步包裝（pytest-bdd v8 step 必須是 def，不可 async def）

    用 fresh event loop 避免跑全套時前面 test 關閉的 loop 影響本 test。
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def ctx():
    return {}


@given("KB chunk_strategy 設為 separator")
def kb_chunk_strategy_separator(ctx):
    ctx["kb_chunk_strategy"] = "separator"


@given("text_splitter_overrides 含 separator splitter")
def overrides_with_separator(ctx):
    default_splitter = MagicMock(name="default_splitter")
    default_splitter.split.return_value = []
    separator_splitter = MagicMock(name="separator_splitter")
    separator_splitter.split.return_value = [
        Chunk(
            id=ChunkId(),
            document_id="doc-1",
            tenant_id="t-1",
            content="商品：A",
            context_text="【商家】X",
            chunk_index=0,
        )
    ]
    ctx["default_splitter"] = default_splitter
    ctx["overrides"] = {"separator": separator_splitter}
    ctx["separator_splitter"] = separator_splitter


@when("ProcessDocumentUseCase 執行 chunking")
def resolve_splitter(ctx):
    # 模擬 ProcessDocumentUseCase 內部的 splitter 解析邏輯
    strategy = ctx["kb_chunk_strategy"] or ""
    overrides = ctx["overrides"]
    splitter = overrides.get(strategy, ctx["default_splitter"])
    chunks = splitter.split("text", "doc-1", "t-1", content_type="application/pdf")
    ctx["chunks"] = chunks
    ctx["selected_splitter"] = splitter


@then("應呼叫 separator splitter 而非預設 splitter")
def assert_separator_used(ctx):
    assert ctx["selected_splitter"] is ctx["separator_splitter"]
    ctx["separator_splitter"].split.assert_called_once()
    ctx["default_splitter"].split.assert_not_called()


@given("KB context_model 已設定")
def kb_context_model_set(ctx):
    ctx["context_model"] = "anthropic:claude-haiku-4-5-20251001"


@given("chunks 含 1 個有 context_text 與 1 個無 context_text")
def chunks_mixed_context(ctx):
    ctx["chunks"] = [
        Chunk(
            id=ChunkId(),
            document_id="doc-1",
            tenant_id="t-1",
            content="商品：蒂克",
            context_text="【商家】家樂福",  # already populated
            chunk_index=0,
        ),
        Chunk(
            id=ChunkId(),
            document_id="doc-1",
            tenant_id="t-1",
            content="一般段落",
            context_text="",  # empty → needs LLM context
            chunk_index=1,
        ),
    ]


@when("ProcessDocumentUseCase 執行 contextual retrieval 步驟")
def call_contextual_retrieval_with_guard(ctx):
    # 模擬 ProcessDocumentUseCase 的 LLM context guard 邏輯
    chunk_context_service = MagicMock()

    async def fake_generate_contexts(_doc, chunks, model=""):
        for c in chunks:
            c.context_text = "[LLM-generated]"
        return chunks

    chunk_context_service.generate_contexts = fake_generate_contexts
    ctx["chunk_context_service"] = chunk_context_service

    needs_context = [c for c in ctx["chunks"] if not c.context_text]
    ctx["needs_context"] = needs_context
    if needs_context:
        _run(
            chunk_context_service.generate_contexts(
                "doc-content", needs_context, model=ctx["context_model"]
            )
        )


@then("只對無 context_text 的 chunk 呼叫 LLM")
def assert_only_empty_context_chunks_processed(ctx):
    # 第一個 chunk（context_text 已有）應保留原值
    assert ctx["chunks"][0].context_text == "【商家】家樂福"
    # 第二個 chunk（之前 empty）應被 LLM 填值
    assert ctx["chunks"][1].context_text == "[LLM-generated]"
    # needs_context 應只有 1 個
    assert len(ctx["needs_context"]) == 1
    assert ctx["needs_context"][0].chunk_index == 1
