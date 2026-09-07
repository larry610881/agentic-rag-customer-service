"""用量記帳覆蓋 BDD Step Definitions（Issue #73）

每條花 token 的路徑都必須留下一筆 usage，且 token 數來自供應商回傳。
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.conversation.search_conversations_use_case import (
    _SYSTEM_TENANT_ID,
    SearchConversationsUseCase,
)
from src.application.knowledge.extract_kb_dm_metadata_use_case import (
    ExtractKBDMMetadataUseCase,
)
from src.application.knowledge.process_document_use_case import (
    ProcessDocumentUseCase,
)
from src.application.knowledge.reembed_chunk_use_case import (
    ReEmbedChunkCommand,
    ReEmbedChunkUseCase,
)
from src.application.knowledge.reprocess_document_use_case import (
    ReprocessDocumentUseCase,
)
from src.application.knowledge.test_retrieval_use_case import (
    TestRetrievalCommand,
    TestRetrievalUseCase,
)
from src.application.memory.extract_memory_use_case import (
    ExtractMemoryCommand,
    ExtractMemoryUseCase,
)
from src.application.rag._hyde_generator import generate_hyde
from src.application.rag._query_rewriter import rewrite_query
from src.application.rag.query_rag_use_case import QueryRAGCommand, QueryRAGUseCase
from src.application.rag.unified_search_use_case import (
    UnifiedSearchCommand,
    UnifiedSearchUseCase,
)
from src.application.usage.embedding_accounting import account_embedding
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.conversation.entity import Message
from src.domain.conversation.history_strategy import HistoryStrategyConfig
from src.domain.conversation.value_objects import MessageId
from src.domain.knowledge.entity import Chunk, Document, KnowledgeBase
from src.domain.knowledge.value_objects import ChunkId, DocumentId
from src.domain.rag.services import EmbeddingResult, EmbeddingService
from src.domain.rag.value_objects import LLMResult, SearchResult, TokenUsage
from src.domain.usage.category import DEPRECATED_CATEGORIES, UsageCategory
from src.infrastructure.conversation.llm_summary_service import (
    LLMConversationSummaryService,
)
from src.infrastructure.conversation.summary_recent_strategy import (
    SummaryRecentStrategy,
)
from src.infrastructure.embedding.cached_embedding_service import (
    CachedEmbeddingService,
    encode_vector,
)
from src.infrastructure.embedding.dynamic_embedding_factory import (
    DynamicEmbeddingServiceProxy,
)
from src.infrastructure.embedding.openai_embedding_service import (
    OpenAIEmbeddingService,
)
from src.infrastructure.llm.llm_caller import LLMCallResult
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)
from tests.unit.knowledge.kb_studio_fixtures import (
    FakeDocumentRepo,
    FakeKbRepo,
    FakeVectorStore,
    make_chunk,
    make_doc,
    make_kb,
)

scenarios("unit/usage/usage_accounting_coverage.feature")

_SRC_DIR = Path(__file__).resolve().parents[3] / "src"
_VECTOR = [0.1] * 8


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _StubEmbedding(EmbeddingService):
    """回固定用量的 embedding 服務（模擬供應商回傳）"""

    def __init__(self, total_tokens: int, *, cache_hit: bool = False) -> None:
        self._total = total_tokens
        self._cache_hit = cache_hit
        self.calls = 0

    async def embed_texts_with_usage(self, texts: list[str]) -> EmbeddingResult:
        self.calls += 1
        return EmbeddingResult(
            vectors=[list(_VECTOR) for _ in texts],
            model="stub-embed",
            total_tokens=self._total,
            cache_hit=self._cache_hit,
        )

    async def embed_query_with_usage(self, text: str) -> EmbeddingResult:
        self.calls += 1
        return EmbeddingResult(
            vectors=[list(_VECTOR)],
            model="stub-embed",
            total_tokens=self._total,
            cache_hit=self._cache_hit,
        )


def _usage_calls(record_usage: AsyncMock, category: str) -> list[dict]:
    return [
        c.kwargs
        for c in record_usage.execute.await_args_list
        if c.kwargs.get("request_type") == category
    ]


@pytest.fixture
def context():
    ctx: dict = {}
    yield ctx
    # 部分 scenario 會啟動 trace，收尾清掉避免污染其他測試
    if ctx.get("trace_started"):
        AgentTraceCollector.finish(0.0)


# ═══════════════════════════════════════════════════════════════════
# Embedding 服務回傳用量
# ═══════════════════════════════════════════════════════════════════


@given(parsers.parse(
    "OpenAI embedding API 回傳 {count:d} 個向量且 usage total_tokens 為 {tokens:d}"
))
def openai_api_returns(context, count, tokens):
    service = OpenAIEmbeddingService(api_key="test-key", model="text-embedding-3-small")

    async def _post(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "data": [{"embedding": list(_VECTOR)} for _ in range(count)],
            "usage": {"total_tokens": tokens},
        }
        return resp

    client = AsyncMock()
    client.post = _post
    service._client = client
    context["service"] = service


@when(parsers.parse("對 {count:d} 筆文字呼叫 embed_texts_with_usage"))
def call_embed_texts_with_usage(context, count):
    texts = [f"文字 {i}" for i in range(count)]
    context["result"] = _run(context["service"].embed_texts_with_usage(texts))


@then(parsers.parse(
    "EmbeddingResult 的 total_tokens 應為 {tokens:d} 且 model 應為服務模型"
))
def verify_openai_result(context, tokens):
    result = context["result"]
    assert isinstance(result, EmbeddingResult)
    assert result.total_tokens == tokens
    assert result.model == "text-embedding-3-small"
    assert result.cache_hit is False


@then(parsers.parse("EmbeddingResult 應含 {count:d} 個向量"))
def verify_vector_count(context, count):
    assert len(context["result"].vectors) == count


def _make_cached(context, *, cached_value, inner_tokens: int):
    inner = AsyncMock()
    inner.embed_query_with_usage = AsyncMock(
        return_value=EmbeddingResult(
            vectors=[list(_VECTOR)], model="inner-model", total_tokens=inner_tokens,
        )
    )
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=cached_value)
    cache.set = AsyncMock()
    context["inner"] = inner
    context["service"] = CachedEmbeddingService(
        inner=inner, cache=cache, model="text-embedding-3-large",
    )


@given(parsers.parse('快取包裝層的快取內已有查詢 "{text}" 的向量'))
def cache_has_vector(context, text):
    _make_cached(context, cached_value=encode_vector(_VECTOR), inner_tokens=99)


@given(parsers.parse("快取包裝層的快取為空且內層服務回傳 total_tokens {tokens:d}"))
def cache_empty(context, tokens):
    _make_cached(context, cached_value=None, inner_tokens=tokens)


@when(parsers.parse('對 "{text}" 呼叫 embed_query_with_usage'))
def call_embed_query_with_usage(context, text):
    context["result"] = _run(context["service"].embed_query_with_usage(text))


@then(parsers.parse(
    "結果 cache_hit 應為 {hit} 且 total_tokens 應為 {tokens:d}"
))
def verify_cache_result(context, hit, tokens):
    result = context["result"]
    assert result.cache_hit is (hit == "true")
    assert result.total_tokens == tokens
    assert result.vectors[0] == pytest.approx(_VECTOR)


@then("內層 embedding 服務不應被呼叫")
def inner_not_called(context):
    context["inner"].embed_query_with_usage.assert_not_awaited()


@given(parsers.parse("動態代理的內層服務回傳 total_tokens {tokens:d}"))
def proxy_inner(context, tokens):
    inner = AsyncMock()
    inner.embed_texts_with_usage = AsyncMock(
        return_value=EmbeddingResult(
            vectors=[list(_VECTOR)], model="inner-model", total_tokens=tokens,
        )
    )
    factory = AsyncMock()
    factory.get_service = AsyncMock(return_value=inner)
    context["inner"] = inner
    context["service"] = DynamicEmbeddingServiceProxy(factory=factory)


@when("透過動態代理呼叫 embed_texts_with_usage")
def proxy_call(context):
    context["result"] = _run(context["service"].embed_texts_with_usage(["甲"]))


@then(parsers.parse("結果 total_tokens 應為 {tokens:d}"))
def verify_total_tokens(context, tokens):
    assert context["result"].total_tokens == tokens
    context["inner"].embed_texts_with_usage.assert_awaited_once_with(["甲"])


# ── account_embedding helper ──


@given("已注入可用的 record_usage")
def inject_record_usage(context):
    context["record_usage"] = AsyncMock()


@given("注入的 record_usage 執行時會拋出例外")
def inject_failing_record_usage(context):
    record_usage = AsyncMock()
    record_usage.execute = AsyncMock(side_effect=RuntimeError("db down"))
    context["record_usage"] = record_usage


@when("以 cache_hit 的 EmbeddingResult 呼叫 account_embedding")
def account_cache_hit(context):
    result = EmbeddingResult(
        vectors=[list(_VECTOR)], model="m", total_tokens=50, cache_hit=True,
    )
    context["recorded"] = _run(account_embedding(
        context["record_usage"],
        tenant_id="tenant-001",
        result=result,
        category=UsageCategory.QUERY_EMBEDDING,
    ))


@when(parsers.parse(
    "以 total_tokens {tokens:d} 的 EmbeddingResult 呼叫 account_embedding"
))
def account_normal(context, tokens):
    result = EmbeddingResult(vectors=[list(_VECTOR)], model="m", total_tokens=tokens)
    try:
        context["recorded"] = _run(account_embedding(
            context["record_usage"],
            tenant_id="tenant-001",
            result=result,
            category=UsageCategory.EMBEDDING,
        ))
        context["error"] = None
    except Exception as exc:  # pragma: no cover - 失敗時保留給 Then 判斷
        context["error"] = exc


@then("record_usage 不應被呼叫")
def record_usage_not_called(context):
    context["record_usage"].execute.assert_not_awaited()
    assert context["recorded"] is False


@then("account_embedding 不應拋出例外")
def account_no_raise(context):
    assert context["error"] is None
    assert context["recorded"] is False
    context["record_usage"].execute.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════
# 文件管線（process / reprocess）
# ═══════════════════════════════════════════════════════════════════


@given(parsers.parse('文件管線 "{pipeline}" 已注入 record_usage'))
def pipeline_setup(context, pipeline):
    raw_text = "這是一段夠長可以切塊的文件內容，用來驗證文件管線的記帳行為。" * 5
    doc = Document(
        id=DocumentId(value="doc-1"),
        kb_id="kb-1",
        tenant_id="tenant-001",
        filename="test.txt",
        content_type="text/plain",
        content="",
        raw_content=raw_text.encode("utf-8"),
        status="pending",
    )
    doc_repo = AsyncMock()
    doc_repo.find_by_id = AsyncMock(return_value=doc)
    task_repo = AsyncMock()
    kb_repo = AsyncMock()
    kb_repo.find_by_id = AsyncMock(return_value=KnowledgeBase(
        ocr_mode="general", context_model="anthropic:claude-haiku-4-5",
    ))
    splitter = MagicMock()
    splitter.split.return_value = [
        Chunk(
            id=ChunkId(value="c-1"),
            document_id="doc-1",
            tenant_id="tenant-001",
            content="這是一個夠長的測試用 chunk 內容，包含中文與英文 mixed text",
            context_text="",
            chunk_index=0,
        )
    ]
    language_detector = MagicMock()
    language_detector.detect.return_value = "zh"
    file_storage = AsyncMock()
    file_storage.load = AsyncMock(side_effect=FileNotFoundError)

    context.update(
        pipeline=pipeline,
        doc=doc,
        doc_repo=doc_repo,
        task_repo=task_repo,
        kb_repo=kb_repo,
        splitter=splitter,
        language_detector=language_detector,
        file_storage=file_storage,
        vector_store=AsyncMock(),
        record_usage=AsyncMock(),
    )


@given(parsers.parse("文件解析消耗 OCR input {inp:d} output {out:d}"))
def parser_tokens(context, inp, out):
    parser = MagicMock()
    parser.parse.return_value = "parsed content " * 20
    parser.last_input_tokens = inp
    parser.last_output_tokens = out
    parser.last_model = "anthropic:ocr-model"
    context["file_parser"] = parser


@given(parsers.parse("上下文服務消耗 input {inp:d} output {out:d}"))
def context_service_tokens(context, inp, out):
    svc = AsyncMock()
    svc.generate_contexts = AsyncMock(return_value=[])
    svc.last_input_tokens = inp
    svc.last_output_tokens = out
    svc.last_cache_read_tokens = 0
    svc.last_cache_creation_tokens = 0
    svc.last_model = "anthropic:ctx-model"
    context["context_service"] = svc


@given(parsers.parse("embedding 服務回傳 total_tokens {tokens:d}"))
def embedding_tokens(context, tokens):
    context["embedding"] = _StubEmbedding(tokens)


@when("執行文件管線")
def run_pipeline(context):
    kwargs = {
        "document_repository": context["doc_repo"],
        "processing_task_repository": context["task_repo"],
        "knowledge_base_repository": context["kb_repo"],
        "text_splitter_service": context["splitter"],
        "embedding_service": context["embedding"],
        "vector_store": context["vector_store"],
        "language_detection_service": context["language_detector"],
        "file_parser_service": context["file_parser"],
        "document_file_storage": context["file_storage"],
        "record_usage_use_case": context["record_usage"],
        "chunk_context_service": context["context_service"],
    }
    if context["pipeline"] == "process":
        use_case = ProcessDocumentUseCase(**kwargs)
    else:
        use_case = ReprocessDocumentUseCase(**kwargs)
    _run(use_case.execute("doc-1", "task-1"))


@then(parsers.parse(
    '應記錄 request_type "{category}" 的用量 input {inp:d} output {out:d}'
))
def usage_recorded_in_out(context, category, inp, out):
    calls = _usage_calls(context["record_usage"], category)
    assert calls, f"沒有 request_type={category!r} 的紀錄"
    usage = calls[0]["usage"]
    assert usage.input_tokens == inp
    assert usage.output_tokens == out


@then(parsers.parse(
    '應記錄 request_type "{category}" 的用量 input {inp:d} 且 kb_id 為文件的 kb'
))
def usage_recorded_with_kb(context, category, inp):
    calls = _usage_calls(context["record_usage"], category)
    assert calls, f"沒有 request_type={category!r} 的紀錄"
    assert calls[0]["usage"].input_tokens == inp
    assert calls[0]["usage"].output_tokens == 0
    assert calls[0]["kb_id"] == context["doc"].kb_id
    assert calls[0]["tenant_id"] == context["doc"].tenant_id


# ═══════════════════════════════════════════════════════════════════
# 查詢 embedding
# ═══════════════════════════════════════════════════════════════════


def _make_query_rag(context, embed: _StubEmbedding, *, tenant_id="T001", kb_id="kb-1"):
    kb_repo = FakeKbRepo()
    vs = FakeVectorStore()
    _run(kb_repo.save(make_kb(kb_id, tenant_id)))
    vs.search_results = [
        SearchResult(
            id=f"c-{i}",
            score=0.9 - i * 0.1,
            payload={
                "content": f"片段 {i}",
                "tenant_id": tenant_id,
                "document_id": "d1",
                "document_name": "doc",
            },
        )
        for i in range(3)
    ]
    record_usage = AsyncMock()
    rag_uc = QueryRAGUseCase(
        knowledge_base_repository=kb_repo,
        embedding_service=embed,
        vector_store=vs,
        llm_service=None,
        record_usage=record_usage,
    )
    context.update(
        kb_repo=kb_repo, vs=vs, embed=embed, rag_uc=rag_uc,
        record_usage=record_usage, tenant_id=tenant_id, kb_id=kb_id,
    )


@given(parsers.parse(
    "檢索用例已注入 record_usage 且 embedding 服務每次回傳 {tokens:d} tokens"
))
def query_rag_setup(context, tokens):
    _make_query_rag(context, _StubEmbedding(tokens))


@given("檢索用例已注入 record_usage 且 embedding 服務回傳 cache_hit")
def query_rag_cache_hit(context):
    _make_query_rag(context, _StubEmbedding(7, cache_hit=True))


@when(parsers.parse('以進入路徑 "{entry}" 執行檢索'))
def run_retrieval(context, entry):
    tenant_id, kb_id = context["tenant_id"], context["kb_id"]
    if entry == "command_bot_id":
        _run(context["rag_uc"].retrieve(QueryRAGCommand(
            tenant_id=tenant_id, kb_id=kb_id, query="退貨", bot_id="bot-fast",
        )))
    elif entry == "trace_context":
        AgentTraceCollector.start(
            tenant_id=tenant_id, agent_mode="react", bot_id="bot-tool",
        )
        context["trace_started"] = True
        _run(context["rag_uc"].retrieve(QueryRAGCommand(
            tenant_id=tenant_id, kb_id=kb_id, query="退貨",
        )))
    elif entry == "playground":
        uc = TestRetrievalUseCase(
            kb_repo=context["kb_repo"],
            embedding_service=context["embed"],
            vector_store=context["vs"],
            record_usage_use_case=context["record_usage"],
            query_rag_use_case=context["rag_uc"],
        )
        _run(uc.execute(TestRetrievalCommand(
            kb_id=kb_id, tenant_id=tenant_id, query="退貨", bot_id="bot-pg",
        )))
    elif entry == "unified_search":
        uc = UnifiedSearchUseCase(
            kb_repo=context["kb_repo"], query_rag_use_case=context["rag_uc"],
        )
        _run(uc.execute(UnifiedSearchCommand(
            tenant_id=tenant_id, kb_ids=[kb_id], query="退貨",
        )))
    else:  # pragma: no cover
        raise AssertionError(f"unknown entry {entry}")


@then(parsers.parse('應記錄 request_type "{category}" 的用量 input {inp:d}'))
def usage_recorded_input(context, category, inp):
    calls = _usage_calls(context["record_usage"], category)
    assert calls, f"沒有 request_type={category!r} 的紀錄"
    for call in calls:
        assert call["usage"].input_tokens == inp
        assert call["usage"].output_tokens == 0
        assert call["usage"].model == "stub-embed"
        assert call["tenant_id"]


@then(parsers.parse('所有 "{category}" 紀錄的 bot_id 應為 "{bot_id}"'))
def usage_bot_id(context, category, bot_id):
    expected = None if bot_id == "none" else bot_id  # "none" = 無 bot 歸屬（/search）
    calls = _usage_calls(context["record_usage"], category)
    assert calls
    assert [c.get("bot_id") for c in calls] == [expected] * len(calls)


@then(parsers.parse('不應有 request_type "{category}" 的紀錄'))
def no_usage_recorded(context, category):
    assert _usage_calls(context["record_usage"], category) == []
    assert context["embed"].calls >= 1  # 確實有走 embedding（只是命中快取）


# ═══════════════════════════════════════════════════════════════════
# reembed / 對話搜尋 / 摘要服務 / DM 中繼資料
# ═══════════════════════════════════════════════════════════════════


@given(parsers.parse("reembed 用例的 embedding 服務回傳 total_tokens {tokens:d}"))
def reembed_setup(context, tokens):
    doc_repo = FakeDocumentRepo()
    kb_repo = FakeKbRepo()
    _run(kb_repo.save(make_kb("kb-1", "T001")))
    _run(doc_repo.save(make_doc("doc-1", "kb-1", "T001")))
    _run(doc_repo.save_chunks([make_chunk("chunk-1", "doc-1", "T001", content="內容")]))
    context.update(
        doc_repo=doc_repo, kb_repo=kb_repo, embed=_StubEmbedding(tokens),
        vs=FakeVectorStore(), record_usage=AsyncMock(),
    )


@when("執行單 chunk 重新向量化")
def run_reembed(context):
    uc = ReEmbedChunkUseCase(
        document_repo=context["doc_repo"],
        kb_repo=context["kb_repo"],
        embedding_service=context["embed"],
        vector_store=context["vs"],
        record_usage=context["record_usage"],
    )
    _run(uc.execute(ReEmbedChunkCommand(chunk_id="chunk-1")))


@given(parsers.parse("對話搜尋用例的 embedding 服務回傳 total_tokens {tokens:d}"))
def conv_search_setup(context, tokens):
    conv_repo = AsyncMock()
    conv_repo.find_by_ids = AsyncMock(return_value=[])
    tenant_repo = AsyncMock()
    tenant_repo.find_all = AsyncMock(return_value=[])
    vector_store = AsyncMock()
    vector_store.search_conv_summaries = AsyncMock(return_value=[])
    context["record_usage"] = AsyncMock()
    context["use_case"] = SearchConversationsUseCase(
        conversation_repository=conv_repo,
        tenant_repository=tenant_repo,
        embedding_service=_StubEmbedding(tokens),
        vector_store=vector_store,
        record_usage=context["record_usage"],
    )


@when("執行對話摘要語意搜尋")
def run_conv_search(context):
    _run(context["use_case"].search_by_semantic(query="退貨糾紛"))


@then("該筆紀錄的 tenant 應為系統租戶")
def usage_system_tenant(context):
    calls = _usage_calls(context["record_usage"], UsageCategory.EMBEDDING.value)
    assert calls[0]["tenant_id"] == _SYSTEM_TENANT_ID


@given(parsers.parse(
    "摘要服務的 LLM 回傳摘要且 embedding 服務回傳 total_tokens {tokens:d}"
))
def summary_service_setup(context, tokens):
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value=LLMResult(
        text="客戶詢問退貨流程，已解答",
        usage=TokenUsage(model="m", input_tokens=100, output_tokens=20),
    ))
    context["service"] = LLMConversationSummaryService(
        llm_service=llm, embedding_service=_StubEmbedding(tokens),
    )


@when("執行對話摘要")
def run_summary_service(context):
    context["result"] = _run(context["service"].summarize(
        messages=[{"role": "user", "content": "我要退貨"}],
    ))


@then(parsers.parse("摘要結果的 embedding_tokens 應為 {tokens:d}"))
def verify_summary_embedding_tokens(context, tokens):
    assert context["result"].embedding_tokens == tokens
    assert context["result"].embedding_model == "stub-embed"


@given(parsers.parse("DM 中繼資料抽取器消耗 input {inp:d} output {out:d}"))
def dm_metadata_setup(context, inp, out):
    kb_repo = AsyncMock()
    kb_repo.find_by_id = AsyncMock(return_value=KnowledgeBase(
        id="kb-1", tenant_id="tenant-001", name="kb", dm_metadata_model="anthropic:m",
    ))
    kb_repo.update = AsyncMock()
    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value={"dm_period": "2026/09"})
    extractor.last_input_tokens = inp
    extractor.last_output_tokens = out
    extractor.last_cache_read_tokens = 0
    extractor.last_cache_creation_tokens = 0
    extractor.last_model = "anthropic:m"
    context["record_usage"] = AsyncMock()
    use_case = ExtractKBDMMetadataUseCase(
        knowledge_base_repository=kb_repo,
        document_repository=AsyncMock(),
        extractor=extractor,
        record_usage=context["record_usage"],
    )

    async def _stub_collect(_kb_id):
        return (["[Page 1]\n【DM 期間】9/1-9/30"], ["cover"])

    use_case._collect_excerpts = _stub_collect  # type: ignore[method-assign]
    context["use_case"] = use_case


@when("執行 DM 中繼資料抽取")
def run_dm_metadata(context):
    _run(context["use_case"].execute("kb-1", "tenant-001"))


# ═══════════════════════════════════════════════════════════════════
# 輔助 LLM bot_id 歸屬
# ═══════════════════════════════════════════════════════════════════


@given(parsers.parse('輔助 LLM 路徑 "{path}" 已注入 record_usage'))
def aux_path_setup(context, path):
    context["path"] = path
    context["record_usage"] = AsyncMock()
    context["llm_result"] = LLMCallResult(
        text="輔助輸出", input_tokens=120, output_tokens=8, model="claude-haiku-4-5",
    )


def _messages(n: int) -> list[Message]:
    return [
        Message(
            id=MessageId(value=f"m{i}"), conversation_id="c1",
            role="user" if i % 2 == 0 else "assistant", content=f"訊息 {i}",
            created_at=datetime.now(timezone.utc),
        )
        for i in range(n)
    ]


@when(parsers.parse('以 bot "{bot_id}" 執行輔助 LLM 路徑'))
def run_aux_path(context, bot_id):
    path = context["path"]
    record_usage = context["record_usage"]
    if path == "rerank":
        _make_query_rag(context, _StubEmbedding(1))
        context["record_usage"] = record_usage = context["record_usage"]
        rerank = AsyncMock(return_value=[{"_idx": 0}])
        with patch("src.application.rag.query_rag_use_case.llm_rerank", rerank):
            _run(context["rag_uc"].retrieve(QueryRAGCommand(
                tenant_id=context["tenant_id"], kb_id=context["kb_id"],
                query="退貨", top_k=1, rerank_enabled=True, bot_id=bot_id,
            )))
        context["aux_bot_id"] = rerank.call_args.kwargs.get("bot_id")
        return
    if path in ("query_rewrite", "hyde"):
        fn = rewrite_query if path == "query_rewrite" else generate_hyde
        with patch(
            "src.infrastructure.llm.llm_caller.call_llm",
            AsyncMock(return_value=context["llm_result"]),
        ):
            _run(fn(
                "原始問題",
                api_key_resolver=AsyncMock(return_value="key"),
                record_usage=record_usage,
                tenant_id="tenant-001",
                bot_id=bot_id,
            ))
    elif path == "history_summary":
        llm = AsyncMock()
        llm.generate = AsyncMock(return_value=LLMResult(
            text="摘要",
            usage=TokenUsage(model="m", input_tokens=400, output_tokens=60),
        ))
        strategy = SummaryRecentStrategy(llm_service=llm, record_usage=record_usage)
        _run(strategy.process(
            _messages(8),
            HistoryStrategyConfig(
                recent_turns=1, tenant_id="tenant-001", bot_id=bot_id,
            ),
        ))
    elif path == "memory_extraction":
        async def _extract(**kwargs):
            kwargs["usage_collector"]["usage"] = TokenUsage(
                model="m", input_tokens=300, output_tokens=50,
            )
            return []

        extraction = AsyncMock()
        extraction.extract_facts = AsyncMock(side_effect=_extract)
        repo = AsyncMock()
        repo.find_by_profile = AsyncMock(return_value=[])
        uc = ExtractMemoryUseCase(
            memory_fact_repository=repo,
            extraction_service=extraction,
            record_usage=record_usage,
        )
        _run(uc.execute(ExtractMemoryCommand(
            profile_id="p1", tenant_id="tenant-001", conversation_id="c1",
            messages=[{"role": "user", "content": "hi"}], bot_id=bot_id,
        )))
    else:  # pragma: no cover
        raise AssertionError(f"unknown path {path}")
    record_usage.execute.assert_awaited_once()
    context["aux_bot_id"] = record_usage.execute.call_args.kwargs.get("bot_id")


@then(parsers.parse('該筆用量紀錄的 bot_id 應為 "{bot_id}"'))
def verify_aux_bot_id(context, bot_id):
    assert context["aux_bot_id"] == bot_id


# ═══════════════════════════════════════════════════════════════════
# 死值清理與 enum 守門
# ═══════════════════════════════════════════════════════════════════


@given("一個 RecordUsageUseCase")
def record_usage_use_case(context):
    context["usage_repo"] = AsyncMock()
    context["use_case"] = RecordUsageUseCase(usage_repository=context["usage_repo"])


@when(parsers.parse('以 request_type "{category}" 寫入用量'))
def write_with_category(context, category):
    assert category in DEPRECATED_CATEGORIES
    assert category in {c.value for c in UsageCategory}  # 讀取相容仍保留
    try:
        _run(context["use_case"].execute(
            tenant_id="tenant-001",
            request_type=category,
            usage=TokenUsage(model="m", input_tokens=10, output_tokens=5),
        ))
        context["error"] = None
    except ValueError as exc:
        context["error"] = exc


@then("應拋出 ValueError 且 usage repository 不應被呼叫")
def verify_rejected(context):
    assert isinstance(context["error"], ValueError)
    context["usage_repo"].save.assert_not_awaited()


_LITERAL_RE = re.compile(r"""request_type\s*=\s*["']""")


@when("掃描 src 目錄中的 request_type 字串字面值")
def scan_literals(context):
    hits: list[str] = []
    for path in sorted(_SRC_DIR.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _LITERAL_RE.search(line):
                hits.append(f"{path.relative_to(_SRC_DIR)}:{lineno}: {line.strip()}")
    context["literal_hits"] = hits


@then("不應有任何檔案使用 request_type 字串字面值")
def verify_no_literals(context):
    assert context["literal_hits"] == [], (
        "request_type 必須使用 UsageCategory enum：\n"
        + "\n".join(context["literal_hits"])
    )


@when("掃描 src 目錄中每個 UsageCategory 成員的引用")
def scan_producers(context):
    corpus = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(_SRC_DIR.rglob("*.py"))
        if path.name != "category.py"
    )
    missing = [
        member.name
        for member in UsageCategory
        if member.value not in DEPRECATED_CATEGORIES
        and f"UsageCategory.{member.name}" not in corpus
    ]
    context["missing_producers"] = missing


@then("每個未淘汰的類別都應在 src 中被引用")
def verify_producers(context):
    assert context["missing_producers"] == [], (
        f"以下 UsageCategory 沒有生產者：{context['missing_producers']}"
    )
