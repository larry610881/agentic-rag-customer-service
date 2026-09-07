"""OCR 引擎多供應商選擇 BDD Step Definitions（Issue #78）"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge._ocr_pipeline import select_ocr_engine
from src.application.knowledge.create_knowledge_base_use_case import (
    CreateKnowledgeBaseCommand,
    CreateKnowledgeBaseUseCase,
)
from src.application.knowledge.process_document_use_case import (
    ProcessDocumentUseCase,
)
from src.application.knowledge.reprocess_document_use_case import (
    ReprocessDocumentUseCase,
)
from src.application.knowledge.update_knowledge_base_use_case import (
    UpdateKnowledgeBaseCommand,
    UpdateKnowledgeBaseUseCase,
)
from src.domain.knowledge.entity import Document, KnowledgeBase
from src.domain.knowledge.ocr_model_spec import parse_ocr_model_spec
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.knowledge.value_objects import DocumentId
from src.domain.shared.exceptions import OcrProcessingError, ValidationError
from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository
from src.infrastructure.file_parser.ocr_engines.base import (
    OcrClassifyResult,
    OcrEngine,
    OcrPageResult,
)
from src.infrastructure.file_parser.ocr_engines.claude_vision_ocr import (
    ClaudeVisionOcrEngine,
)
from src.infrastructure.file_parser.ocr_engines.factory import (
    DynamicOcrEngineFactory,
)
from src.infrastructure.file_parser.ocr_engines.openai_compat_vision_ocr import (
    OpenAICompatVisionOcrEngine,
)
from src.infrastructure.file_parser.ocr_file_parser_service import (
    OcrFileParserService,
)

scenarios("unit/knowledge/ocr_engine_selection.feature")

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _resolver(_provider: str) -> str:
    return "test-key"


async def _empty_resolver(_provider: str) -> str:
    return ""


class _FakeEngine(OcrEngine):
    """固定回傳 token 數的假引擎（驗證用量流向記帳）。"""

    def __init__(self, spec: str, input_tokens: int, output_tokens: int) -> None:
        self._spec = spec
        self._in = input_tokens
        self._out = output_tokens

    @property
    def model_spec(self) -> str:
        return self._spec

    async def ocr_page_with_usage(
        self, image_bytes: bytes, prompt: str | None = None
    ) -> OcrPageResult:
        await asyncio.sleep(0)  # 讓並行的另一份文件有機會交錯執行
        return OcrPageResult(
            text=f"text from {self._spec}",
            input_tokens=self._in,
            output_tokens=self._out,
            model=self._spec,
        )

    async def classify_page_type_with_usage(
        self, image_bytes: bytes
    ) -> OcrClassifyResult:
        return OcrClassifyResult(page_type="catalog", model=self._spec)


@pytest.fixture
def context():
    return {"requests": [], "docs": {}}


# ── Background ──


@given(parsers.re(r'環境預設 OCR 模型為 "(?P<spec>.*)"'))
def env_default(context, spec):
    factory = DynamicOcrEngineFactory(api_key_resolver=_resolver, default_spec=spec)
    context["factory"] = factory
    context["parser"] = OcrFileParserService(engine_factory=factory)
    context["kb"] = KnowledgeBase(tenant_id="t-1", ocr_mode="catalog")
    context["tenant"] = Tenant(default_ocr_model="")


# ── 引擎選擇 ──


@given(parsers.re(r'知識庫 ocr_model 為 "(?P<spec>.*)"'))
def kb_spec(context, spec):
    context["kb"] = KnowledgeBase(
        tenant_id="t-1", ocr_mode="catalog", ocr_model=spec
    )


@given(parsers.re(r'租戶 default_ocr_model 為 "(?P<spec>.*)"'))
def tenant_spec(context, spec):
    context["tenant"] = Tenant(default_ocr_model=spec)


def _tenant_repo(context) -> AsyncMock:
    repo = AsyncMock(spec=TenantRepository)
    repo.find_by_id = AsyncMock(return_value=context["tenant"])
    return repo


def _select(context):
    return _run(
        select_ocr_engine(
            context["parser"],
            kb=context["kb"],
            tenant_repo=_tenant_repo(context),
            tenant_id="t-1",
        )
    )


@when("解析 OCR 引擎")
def resolve_engine(context):
    context["engine"], context["spec"] = _select(context)


@when("解析 OCR 引擎兩次")
def resolve_engine_twice(context):
    context["engine"], context["spec"] = _select(context)
    context["engine_2"], _ = _select(context)


@then("應選用 OpenAI 相容視覺引擎")
def is_compat(context):
    assert isinstance(context["engine"], OpenAICompatVisionOcrEngine)


@then("應選用 Claude Vision 引擎")
def is_claude(context):
    assert isinstance(context["engine"], ClaudeVisionOcrEngine)


@then(parsers.parse('引擎 base_url 應為 "{url}"'))
def base_url_is(context, url):
    assert context["engine"].base_url == url


@then(parsers.parse('引擎 model spec 應為 "{spec}"'))
def spec_is(context, spec):
    assert context["engine"].model_spec == spec
    assert context["spec"] == spec


@then("兩次應取得同一個引擎實例")
def same_instance(context):
    assert context["engine"] is context["engine_2"]


# ── KB 儲存驗證 ──


@when(parsers.re(r'以 ocr_model "(?P<spec>.*)" 建立知識庫'))
def create_kb(context, spec):
    repo = AsyncMock(spec=KnowledgeBaseRepository)
    context["kb_repo"] = repo
    context["error"] = None
    try:
        _run(
            CreateKnowledgeBaseUseCase(repo).execute(
                CreateKnowledgeBaseCommand(
                    tenant_id="t-1", name="kb", ocr_model=spec
                )
            )
        )
    except ValidationError as e:
        context["error"] = e


@given("一個既有知識庫")
def existing_kb(context):
    repo = AsyncMock(spec=KnowledgeBaseRepository)
    repo.find_by_id = AsyncMock(
        return_value=KnowledgeBase(tenant_id="t-1", name="kb")
    )
    context["kb_repo"] = repo


@when(parsers.re(r'以 ocr_model "(?P<spec>.*)" 更新知識庫'))
def update_kb(context, spec):
    repo = context["kb_repo"]
    context["error"] = None
    try:
        _run(
            UpdateKnowledgeBaseUseCase(repo).execute(
                UpdateKnowledgeBaseCommand(
                    kb_id="kb-1", requester_tenant_id="t-1", ocr_model=spec
                )
            )
        )
    except ValidationError as e:
        context["error"] = e


@then(parsers.parse('應回傳驗證錯誤且訊息包含 "{text}"'))
def validation_error(context, text):
    assert isinstance(context["error"], ValidationError)
    assert text in context["error"].message


@then("知識庫不應被儲存")
def kb_not_saved(context):
    context["kb_repo"].save.assert_not_called()


@then("知識庫不應被更新")
def kb_not_updated(context):
    context["kb_repo"].update.assert_not_called()


@then(parsers.re(r'知識庫應更新 ocr_model 為 "(?P<spec>.*)"'))
def kb_updated_with(context, spec):
    assert context["error"] is None
    context["kb_repo"].update.assert_awaited_once()
    assert context["kb_repo"].update.call_args.kwargs["ocr_model"] == spec


# ── OpenAI 相容引擎 ──


def _build_compat(context, spec: str, resolver) -> None:
    provider, model = parse_ocr_model_spec(spec)

    def handler(request: httpx.Request) -> httpx.Response:
        context["requests"].append(request)
        status, body = context.get("response", (200, {}))
        return httpx.Response(status, json=body)

    context["engine"] = OpenAICompatVisionOcrEngine(
        api_key_resolver=resolver,
        provider=provider,
        model=model,
        transport=httpx.MockTransport(handler),
    )


@given(parsers.parse('一個 google 相容引擎 "{spec}"'))
def compat_engine(context, spec):
    _build_compat(context, spec, _resolver)


@given(parsers.parse('一個 google 相容引擎 "{spec}" 且供應商未設定 API key'))
def compat_engine_no_key(context, spec):
    _build_compat(context, spec, _empty_resolver)


@given(
    parsers.re(
        r'相容端點回應文字 "(?P<text>.*)" 且用量 prompt_tokens (?P<n>\d+)'
        r"、completion_tokens (?P<m>\d+)"
    )
)
def compat_response(context, text, n, m):
    content = text.replace('\\"', '"')
    context["response"] = (
        200,
        {
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": int(n), "completion_tokens": int(m)},
        },
    )


@given("相容端點回應 HTTP 401")
def compat_401(context):
    context["response"] = (401, {"error": {"message": "invalid api key"}})


@when("對一張 PNG 圖片執行 OCR")
def run_ocr(context):
    context["error"] = None
    try:
        context["result"] = _run(
            context["engine"].ocr_page_with_usage(PNG_BYTES, "商品 prompt")
        )
    except OcrProcessingError as e:
        context["error"] = e


@when("對一張 PNG 圖片執行頁面分類")
def run_classify(context):
    context["result"] = _run(
        context["engine"].classify_page_type_with_usage(PNG_BYTES)
    )


def _sent_body(context) -> dict:
    assert context["requests"], "沒有送出任何請求"
    return json.loads(context["requests"][-1].content)


@then(parsers.parse('OCR 結果文字應為 "{text}"'))
def ocr_text_is(context, text):
    assert context["result"].text == text


@then(parsers.parse("OCR 結果 input_tokens 應為 {n:d}、output_tokens 應為 {m:d}"))
def ocr_tokens(context, n, m):
    assert context["result"].input_tokens == n
    assert context["result"].output_tokens == m


@then(parsers.parse('OCR 結果 model 應為 "{spec}"'))
def ocr_model_is(context, spec):
    assert context["result"].model == spec


@then(parsers.parse('送出的請求應以 image_url data URL 附上 "{mime}" 圖片'))
def request_has_image(context, mime):
    body = _sent_body(context)
    parts = body["messages"][0]["content"]
    image = next(p for p in parts if p["type"] == "image_url")
    assert image["image_url"]["url"].startswith(f"data:{mime};base64,")
    assert body["model"] == context["engine"].model_spec.split(":", 1)[1]


@then("送出的 prompt 應包含抑制幻覺指令")
def request_has_anti_hallucination(context):
    parts = _sent_body(context)["messages"][0]["content"]
    text = next(p for p in parts if p["type"] == "text")["text"]
    assert "商品 prompt" in text
    assert "不可補字" in text
    assert "不得推測數字" in text


@then("送出的請求應包含 json_schema response_format")
def request_has_json_schema(context):
    rf = _sent_body(context)["response_format"]
    assert rf["type"] == "json_schema"
    enum = rf["json_schema"]["schema"]["properties"]["page_type"]["enum"]
    assert set(enum) == {"catalog", "promotion", "mixed", "cover"}


@then("送出的請求不應包含 response_format")
def request_without_response_format(context):
    assert "response_format" not in _sent_body(context)


@then(parsers.parse('頁面分類結果應為 "{page_type}"'))
def classify_is(context, page_type):
    assert context["result"].page_type == page_type


@then(parsers.parse("分類結果 input_tokens 應為 {n:d}、output_tokens 應為 {m:d}"))
def classify_tokens(context, n, m):
    assert context["result"].input_tokens == n
    assert context["result"].output_tokens == m


@then(parsers.parse('應拋出 OcrProcessingError 且訊息包含 "{text}"'))
def raises_ocr_error(context, text):
    assert isinstance(context["error"], OcrProcessingError)
    assert text in str(context["error"])
    assert not context["requests"] or context["requests"][-1] is not None


# ── 用量記帳（ProcessDocument / ReprocessDocument）──


def _install_fake_engines(context, tokens_by_spec: dict[str, tuple[int, int]]):
    """讓 factory 對任一 spec 建出假引擎（token 數依 spec 查表，缺省 0）。"""
    factory = context["factory"]
    factory._engines.clear()

    def _build(spec: str) -> OcrEngine:
        in_tok, out_tok = tokens_by_spec.get(spec, (0, 0))
        return _FakeEngine(spec, in_tok, out_tok)

    factory._build = _build  # type: ignore[method-assign]


@given(parsers.parse("假引擎每頁回傳 input_tokens {n:d}、output_tokens {m:d}"))
def fake_engine_tokens(context, n, m):
    context["fake_tokens"] = (n, m)

    factory = context["factory"]
    factory._engines.clear()
    factory._build = lambda spec: _FakeEngine(spec, n, m)  # type: ignore[method-assign]


def _png_document(doc_id: str, kb_id: str) -> Document:
    return Document(
        id=DocumentId(value=doc_id),
        kb_id=kb_id,
        tenant_id="t-1",
        filename=f"{doc_id}.png",
        content_type="image/png",
        content="",
        raw_content=PNG_BYTES,
        storage_path="",
    )


def _pipeline_deps(kb: KnowledgeBase, doc: Document) -> dict:
    doc_repo = AsyncMock()
    doc_repo.find_by_id = AsyncMock(return_value=doc)
    doc_repo.find_by_parent_id = AsyncMock(return_value=[])
    task_repo = AsyncMock()
    kb_repo = AsyncMock()
    kb_repo.find_by_id = AsyncMock(return_value=kb)
    splitter = MagicMock()
    splitter.split.return_value = []
    embedding = AsyncMock()
    embedding.embed_documents = AsyncMock(return_value=[])
    vector_store = AsyncMock()
    language_detector = MagicMock()
    language_detector.detect.return_value = "zh"
    file_storage = AsyncMock()
    file_storage.load = AsyncMock(side_effect=FileNotFoundError)
    record_usage = AsyncMock()
    record_usage.execute = AsyncMock()
    return {
        "document_repository": doc_repo,
        "processing_task_repository": task_repo,
        "knowledge_base_repository": kb_repo,
        "text_splitter_service": splitter,
        "embedding_service": embedding,
        "vector_store": vector_store,
        "language_detection_service": language_detector,
        "document_file_storage": file_storage,
        "record_usage_use_case": record_usage,
    }


def _ocr_records(record_usage: AsyncMock) -> list:
    return [
        c.kwargs
        for c in record_usage.execute.call_args_list
        if c.kwargs.get("request_type") == "ocr"
    ]


@when("處理一份 PNG 文件")
def process_png(context):
    kb = context["kb"]
    deps = _pipeline_deps(kb, _png_document("doc-1", "kb-1"))
    context["record_usage"] = deps["record_usage_use_case"]
    use_case = ProcessDocumentUseCase(
        file_parser_service=context["parser"],
        tenant_repository=_tenant_repo(context),
        **deps,
    )
    _run(use_case.execute("doc-1", "task-1"))


@when(parsers.parse('以 ocr_model "{spec}" 重新處理一份 PNG 文件'))
def reprocess_png(context, spec):
    kb = context["kb"]
    deps = _pipeline_deps(kb, _png_document("doc-1", "kb-1"))
    deps["document_repository"].update_status = AsyncMock()
    deps["document_repository"].update_content = AsyncMock()
    deps["document_repository"].delete_chunks_by_document = AsyncMock()
    deps["document_repository"].bulk_save_chunks = AsyncMock()
    deps["vector_store"].ensure_collection = AsyncMock()
    deps["vector_store"].delete = AsyncMock()
    context["record_usage"] = deps["record_usage_use_case"]
    use_case = ReprocessDocumentUseCase(
        file_parser_service=context["parser"],
        tenant_repository=_tenant_repo(context),
        **deps,
    )
    _run(use_case.execute("doc-1", "task-1", ocr_model=spec))


@then(parsers.parse('應記錄一筆 ocr 用量 model 為 "{spec}"'))
def one_ocr_record(context, spec):
    records = _ocr_records(context["record_usage"])
    assert len(records) == 1, records
    assert records[0]["usage"].model == spec
    context["ocr_record"] = records[0]


@then(parsers.parse("該筆用量 input_tokens 應為 {n:d}、output_tokens 應為 {m:d}"))
def record_tokens(context, n, m):
    usage = context["ocr_record"]["usage"]
    assert usage.input_tokens == n
    assert usage.output_tokens == m


# ── 並行 ──


@given(
    parsers.parse(
        '文件 {label} 的知識庫 ocr_model 為 "{spec}" 且假引擎每頁回傳 '
        "input_tokens {n:d}、output_tokens {m:d}"
    )
)
def parallel_doc(context, label, spec, n, m):
    context["docs"][label] = {"spec": spec, "tokens": (n, m)}


@when(parsers.parse("並行處理文件 {a} 與文件 {b}"))
def process_parallel(context, a, b):
    tokens_by_spec = {d["spec"]: d["tokens"] for d in context["docs"].values()}
    _install_fake_engines(context, tokens_by_spec)

    use_cases = {}
    for label in (a, b):
        spec = context["docs"][label]["spec"]
        kb = KnowledgeBase(tenant_id="t-1", ocr_mode="catalog", ocr_model=spec)
        deps = _pipeline_deps(kb, _png_document(f"doc-{label}", f"kb-{label}"))
        context["docs"][label]["record_usage"] = deps["record_usage_use_case"]
        use_cases[label] = ProcessDocumentUseCase(
            file_parser_service=context["parser"],
            tenant_repository=_tenant_repo(context),
            **deps,
        )

    async def _both():
        await asyncio.gather(
            use_cases[a].execute(f"doc-{a}", f"task-{a}"),
            use_cases[b].execute(f"doc-{b}", f"task-{b}"),
        )

    _run(_both())


@then(
    parsers.parse(
        '文件 {label} 應記錄 ocr 用量 model "{spec}" input_tokens {n:d}'
        "、output_tokens {m:d}"
    )
)
def parallel_record(context, label, spec, n, m):
    records = _ocr_records(context["docs"][label]["record_usage"])
    assert len(records) == 1, records
    usage = records[0]["usage"]
    assert usage.model == spec
    assert usage.input_tokens == n
    assert usage.output_tokens == m
