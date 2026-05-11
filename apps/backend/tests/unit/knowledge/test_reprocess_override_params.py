"""Unit tests for ReprocessDocumentUseCase 暫時性 KB 設定覆寫。

驗證 reprocess 接受的 override 參數（ocr_mode / chunk_strategy / context_model）
真實生效，不是 dead code。Override 只影響這次 reprocess，不寫回 KB。

歷史：chunk_strategy 參數從一開始就在 signature 裡但 _resolve_splitter 永遠走
kb.chunk_strategy → 永遠是 dead code。這組測試保證 override 真實作用。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.application.knowledge.reprocess_document_use_case import (
    ReprocessDocumentUseCase,
)
from src.domain.knowledge.entity import Document, KnowledgeBase
from src.domain.knowledge.value_objects import DocumentId


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_real_png_bytes(w: int = 800, h: int = 1200) -> bytes:
    """For tests that exercise sliced OCR helper which uses PIL.Image.open()."""
    import io as _io

    from PIL import Image as _Image

    img = _Image.new("RGB", (w, h), color=(255, 255, 255))
    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_use_case(
    *,
    kb_ocr_mode: str = "general",
    kb_chunk_strategy: str = "",
    kb_context_model: str = "",
    text_splitter_overrides: dict | None = None,
    context_service=None,
    splitter_returns_chunks: bool = False,
):
    """建立 ReprocessDocumentUseCase + mocks。

    splitter_returns_chunks=True 時 splitter.split 回 1 個 chunk，讓 pipeline
    走完完整路徑（不會在「Empty after filter」分支提早 return）。
    """
    doc_repo = AsyncMock()
    doc_repo.find_by_id = AsyncMock(
        return_value=Document(
            id=DocumentId(value="doc-1"),
            kb_id="kb-1",
            tenant_id="t-1",
            filename="test.pdf",
            content_type="application/pdf",
            content="some preexisting content",
            raw_content=b"%PDF-1.4 fake",
        )
    )
    doc_repo.update_status = AsyncMock()
    doc_repo.update_content = AsyncMock()
    doc_repo.update_quality = AsyncMock()
    doc_repo.delete_chunks_by_document = AsyncMock()
    doc_repo.save_chunks = AsyncMock()

    task_repo = AsyncMock()

    kb_repo = AsyncMock()
    kb_repo.find_by_id = AsyncMock(
        return_value=KnowledgeBase(
            ocr_mode=kb_ocr_mode,
            chunk_strategy=kb_chunk_strategy,
            context_model=kb_context_model,
        )
    )

    splitter = MagicMock()
    if splitter_returns_chunks:
        from src.domain.knowledge.entity import Chunk
        from src.domain.knowledge.value_objects import ChunkId

        splitter.split.return_value = [
            Chunk(
                id=ChunkId(value="c-1"),
                document_id="doc-1",
                tenant_id="t-1",
                # ≥ 20 字元才通過 ChunkFilterService.filter（min_length=20）
                content="這是一個夠長的測試用 chunk 內容，包含中文與英文 mixed text",
                context_text="",
                chunk_index=0,
            )
        ]
    else:
        splitter.split.return_value = []

    embedding = AsyncMock()
    embedding.embed_texts = AsyncMock(return_value=[[0.1] * 3072])
    vector_store = AsyncMock()
    language_detector = MagicMock()
    language_detector.detect.return_value = "zh"
    file_storage = AsyncMock()
    file_storage.load = AsyncMock(side_effect=FileNotFoundError)

    file_parser = MagicMock()
    file_parser.parse_pdf_async = AsyncMock(return_value="parsed pdf text")

    return (
        ReprocessDocumentUseCase(
            document_repository=doc_repo,
            processing_task_repository=task_repo,
            knowledge_base_repository=kb_repo,
            text_splitter_service=splitter,
            embedding_service=embedding,
            vector_store=vector_store,
            language_detection_service=language_detector,
            file_parser_service=file_parser,
            document_file_storage=file_storage,
            text_splitter_overrides=text_splitter_overrides or {},
            chunk_context_service=context_service,
        ),
        {
            "doc_repo": doc_repo,
            "kb_repo": kb_repo,
            "splitter": splitter,
            "file_parser": file_parser,
            "context_service": context_service,
        },
    )


# ── ocr_mode override ──


def test_ocr_mode_override_takes_precedence_over_kb():
    """ocr_mode override 應蓋過 kb.ocr_mode 傳給 parse_pdf_async。"""
    use_case, mocks = _make_use_case(kb_ocr_mode="general")
    _run(use_case.execute("doc-1", "task-1", ocr_mode="catalog"))

    mocks["file_parser"].parse_pdf_async.assert_awaited_once()
    call_kwargs = mocks["file_parser"].parse_pdf_async.call_args.kwargs
    assert call_kwargs["ocr_mode"] == "catalog"


def test_ocr_mode_none_falls_back_to_kb():
    """沒給 ocr_mode override → fallback 到 kb.ocr_mode。"""
    use_case, mocks = _make_use_case(kb_ocr_mode="catalog")
    _run(use_case.execute("doc-1", "task-1"))

    call_kwargs = mocks["file_parser"].parse_pdf_async.call_args.kwargs
    assert call_kwargs["ocr_mode"] == "catalog"


# ── chunk_strategy override ──


def test_chunk_strategy_override_takes_precedence_over_kb():
    """chunk_strategy override 應蓋過 kb.chunk_strategy 路由到對應 splitter。"""
    override_splitter = MagicMock()
    override_splitter.split.return_value = []
    use_case, mocks = _make_use_case(
        kb_chunk_strategy="recursive",
        text_splitter_overrides={"separator": override_splitter},
    )
    _run(use_case.execute("doc-1", "task-1", chunk_strategy="separator"))

    # override splitter 應被呼叫；KB 設定的 recursive 不應被選
    override_splitter.split.assert_called_once()
    mocks["splitter"].split.assert_not_called()


def test_chunk_strategy_none_falls_back_to_kb():
    """沒給 chunk_strategy override → 走 kb.chunk_strategy 設定。"""
    kb_splitter = MagicMock()
    kb_splitter.split.return_value = []
    use_case, mocks = _make_use_case(
        kb_chunk_strategy="separator",
        text_splitter_overrides={"separator": kb_splitter},
    )
    _run(use_case.execute("doc-1", "task-1"))

    kb_splitter.split.assert_called_once()


# ── context_model override ──


def test_context_model_override_triggers_contextual_retrieval():
    """context_model override 為非空 → 應呼叫 generate_contexts。"""
    context_service = AsyncMock()
    context_service.generate_contexts = AsyncMock(return_value=[])
    use_case, _ = _make_use_case(
        kb_context_model="",
        context_service=context_service,
        splitter_returns_chunks=True,
    )
    _run(
        use_case.execute(
            "doc-1", "task-1", context_model="anthropic:claude-haiku-4-5"
        )
    )

    context_service.generate_contexts.assert_awaited_once()
    call_kwargs = context_service.generate_contexts.call_args.kwargs
    assert call_kwargs["model"] == "anthropic:claude-haiku-4-5"


def test_context_model_none_falls_back_to_kb_setting():
    """沒給 context_model override → fallback 到 kb.context_model。"""
    context_service = AsyncMock()
    context_service.generate_contexts = AsyncMock(return_value=[])
    use_case, _ = _make_use_case(
        kb_context_model="anthropic:claude-haiku-4-5",
        context_service=context_service,
        splitter_returns_chunks=True,
    )
    _run(use_case.execute("doc-1", "task-1"))

    context_service.generate_contexts.assert_awaited_once()
    call_kwargs = context_service.generate_contexts.call_args.kwargs
    assert call_kwargs["model"] == "anthropic:claude-haiku-4-5"


def test_image_with_auto_mode_uses_page_dispatcher_not_default_prompt():
    """image/png + ocr_mode=auto 必須走 ocr_page_auto_dispatch，
    對齊 process_document（過去 reprocess 永遠走 OCR_PROMPTS['auto'] →
    fallback 到 _DEFAULT_PROMPT → SeparatorTextSplitter sniff 失敗 →
    user 看到「多商品合併到同 chunk」的 drift bug）。
    """
    # 改 document.content_type=image/png + raw_content=BYTEA
    doc_repo = AsyncMock()
    from src.domain.knowledge.entity import Chunk
    from src.domain.knowledge.value_objects import ChunkId

    doc_repo.find_by_id = AsyncMock(
        return_value=Document(
            id=DocumentId(value="img-1"),
            kb_id="kb-1",
            tenant_id="t-1",
            filename="page_051.png",
            content_type="image/png",
            content="",
            raw_content=b"FAKE_PNG_BYTES",
        )
    )
    doc_repo.update_status = AsyncMock()
    doc_repo.update_content = AsyncMock()
    doc_repo.update_quality = AsyncMock()
    doc_repo.delete_chunks_by_document = AsyncMock()
    doc_repo.save_chunks = AsyncMock()
    task_repo = AsyncMock()
    kb_repo = AsyncMock()
    kb_repo.find_by_id = AsyncMock(
        return_value=KnowledgeBase(ocr_mode="auto", chunk_strategy="separator")
    )
    splitter = MagicMock()
    splitter.split.return_value = [
        Chunk(
            id=ChunkId(value="c-1"),
            document_id="img-1",
            tenant_id="t-1",
            content="長到能通過 filter 的內容 sufficient length text body",
            chunk_index=0,
        )
    ]
    embedding = AsyncMock()
    embedding.embed_texts = AsyncMock(return_value=[[0.1] * 3072])
    vector_store = AsyncMock()
    language_detector = MagicMock()
    language_detector.detect.return_value = "zh"
    file_storage = AsyncMock()
    file_storage.load = AsyncMock(side_effect=FileNotFoundError)

    # file_parser._ocr 有 ocr_page_auto_dispatch
    mock_ocr = AsyncMock()
    mock_ocr.ocr_page_auto_dispatch = AsyncMock(
        return_value=("catalog", "=== \n商品：A\n===")
    )
    mock_ocr.ocr_page = AsyncMock()
    file_parser = MagicMock()
    file_parser._ocr = mock_ocr

    use_case = ReprocessDocumentUseCase(
        document_repository=doc_repo,
        processing_task_repository=task_repo,
        knowledge_base_repository=kb_repo,
        text_splitter_service=splitter,
        embedding_service=embedding,
        vector_store=vector_store,
        language_detection_service=language_detector,
        file_parser_service=file_parser,
        document_file_storage=file_storage,
    )
    _run(use_case.execute("img-1", "task-1"))

    # ✅ auto 模式必須走 dispatcher（不是固定 prompt）
    mock_ocr.ocr_page_auto_dispatch.assert_awaited_once()
    # ❌ 絕不應 fallback 到 ocr_page+default prompt
    mock_ocr.ocr_page.assert_not_awaited()


def test_image_with_catalog_mode_uses_static_prompt_path():
    """image/png + ocr_mode=catalog 走 ocr_page + _CATALOG_PROMPT（既有路徑）。"""
    doc_repo = AsyncMock()
    doc_repo.find_by_id = AsyncMock(
        return_value=Document(
            id=DocumentId(value="img-1"),
            kb_id="kb-1",
            tenant_id="t-1",
            filename="page.png",
            content_type="image/png",
            content="",
            raw_content=b"FAKE_PNG",
        )
    )
    doc_repo.update_status = AsyncMock()
    doc_repo.update_content = AsyncMock()
    doc_repo.update_quality = AsyncMock()
    doc_repo.delete_chunks_by_document = AsyncMock()
    doc_repo.save_chunks = AsyncMock()
    task_repo = AsyncMock()
    kb_repo = AsyncMock()
    kb_repo.find_by_id = AsyncMock(
        return_value=KnowledgeBase(ocr_mode="catalog")
    )
    splitter = MagicMock()
    splitter.split.return_value = []
    embedding = AsyncMock()
    vector_store = AsyncMock()
    language_detector = MagicMock()
    language_detector.detect.return_value = "zh"
    file_storage = AsyncMock()
    file_storage.load = AsyncMock(side_effect=FileNotFoundError)

    mock_ocr = AsyncMock()
    mock_ocr.ocr_page_auto_dispatch = AsyncMock()
    mock_ocr.ocr_page = AsyncMock(return_value="text")
    file_parser = MagicMock()
    file_parser._ocr = mock_ocr

    use_case = ReprocessDocumentUseCase(
        document_repository=doc_repo,
        processing_task_repository=task_repo,
        knowledge_base_repository=kb_repo,
        text_splitter_service=splitter,
        embedding_service=embedding,
        vector_store=vector_store,
        language_detection_service=language_detector,
        file_parser_service=file_parser,
        document_file_storage=file_storage,
    )
    _run(use_case.execute("img-1", "task-1"))

    mock_ocr.ocr_page.assert_awaited_once()
    mock_ocr.ocr_page_auto_dispatch.assert_not_awaited()


def test_ocr_slice_grid_override_passed_to_image_pipeline():
    """ocr_slice_grid override 應蓋過 kb.ocr_slice_grid，影響 image/png OCR 路徑。

    驗證方式：image/png + auto mode → 走 slice path（先 classify 再 tile OCR），
    classify_page_type 應被呼叫，ocr_page 應被呼叫 6 次（2x3 = 6 tiles）。
    """
    doc_repo = AsyncMock()
    doc_repo.find_by_id = AsyncMock(
        return_value=Document(
            id=DocumentId(value="img-1"),
            kb_id="kb-1",
            tenant_id="t-1",
            filename="page.png",
            content_type="image/png",
            content="",
            # 用真實 1x1 PNG 而非 fake bytes（slice helper 會用 PIL 打開）
            raw_content=_make_real_png_bytes(),
        )
    )
    doc_repo.update_status = AsyncMock()
    doc_repo.update_content = AsyncMock()
    doc_repo.update_quality = AsyncMock()
    doc_repo.delete_chunks_by_document = AsyncMock()
    doc_repo.save_chunks = AsyncMock()
    task_repo = AsyncMock()
    kb_repo = AsyncMock()
    kb_repo.find_by_id = AsyncMock(
        return_value=KnowledgeBase(
            ocr_mode="auto",
            ocr_slice_grid="",  # KB 預設不切片
        )
    )
    splitter = MagicMock()
    splitter.split.return_value = []
    embedding = AsyncMock()
    vector_store = AsyncMock()
    language_detector = MagicMock()
    language_detector.detect.return_value = "zh"
    file_storage = AsyncMock()
    file_storage.load = AsyncMock(side_effect=FileNotFoundError)

    mock_ocr = AsyncMock()
    mock_ocr.classify_page_type = AsyncMock(return_value="catalog")
    mock_ocr.ocr_page = AsyncMock(return_value="text")
    mock_ocr.ocr_page_auto_dispatch = AsyncMock()
    file_parser = MagicMock()
    file_parser._ocr = mock_ocr

    use_case = ReprocessDocumentUseCase(
        document_repository=doc_repo,
        processing_task_repository=task_repo,
        knowledge_base_repository=kb_repo,
        text_splitter_service=splitter,
        embedding_service=embedding,
        vector_store=vector_store,
        language_detection_service=language_detector,
        file_parser_service=file_parser,
        document_file_storage=file_storage,
    )
    # caller 傳 ocr_slice_grid="2x3"，應蓋過 KB 的 ""
    _run(use_case.execute("img-1", "task-1", ocr_slice_grid="2x3"))

    # ✅ 切片啟用 → classify_page_type 被呼叫一次（決定 tile 用哪個 prompt）
    mock_ocr.classify_page_type.assert_awaited_once()
    # ✅ ocr_page 被呼叫 6 次（2x3 = 6 tiles）
    assert mock_ocr.ocr_page.await_count == 6, (
        f"切片應產生 6 tiles，實際 {mock_ocr.ocr_page.await_count}"
    )
    # ❌ 不走原本的 auto_dispatch（已 override 為切片）
    mock_ocr.ocr_page_auto_dispatch.assert_not_awaited()


def test_ocr_slice_grid_none_falls_back_to_kb_setting():
    """無 override → 走 kb.ocr_slice_grid（不切片）→ 走原 auto_dispatch path。"""
    doc_repo = AsyncMock()
    doc_repo.find_by_id = AsyncMock(
        return_value=Document(
            id=DocumentId(value="img-1"),
            kb_id="kb-1",
            tenant_id="t-1",
            filename="page.png",
            content_type="image/png",
            content="",
            raw_content=_make_real_png_bytes(),
        )
    )
    doc_repo.update_status = AsyncMock()
    doc_repo.update_content = AsyncMock()
    doc_repo.update_quality = AsyncMock()
    doc_repo.delete_chunks_by_document = AsyncMock()
    doc_repo.save_chunks = AsyncMock()
    task_repo = AsyncMock()
    kb_repo = AsyncMock()
    kb_repo.find_by_id = AsyncMock(
        return_value=KnowledgeBase(ocr_mode="auto", ocr_slice_grid="")
    )
    splitter = MagicMock()
    splitter.split.return_value = []
    embedding = AsyncMock()
    vector_store = AsyncMock()
    language_detector = MagicMock()
    language_detector.detect.return_value = "zh"
    file_storage = AsyncMock()
    file_storage.load = AsyncMock(side_effect=FileNotFoundError)

    mock_ocr = AsyncMock()
    mock_ocr.classify_page_type = AsyncMock()
    mock_ocr.ocr_page = AsyncMock()
    mock_ocr.ocr_page_auto_dispatch = AsyncMock(
        return_value=("catalog", "auto-dispatch result")
    )
    file_parser = MagicMock()
    file_parser._ocr = mock_ocr

    use_case = ReprocessDocumentUseCase(
        document_repository=doc_repo,
        processing_task_repository=task_repo,
        knowledge_base_repository=kb_repo,
        text_splitter_service=splitter,
        embedding_service=embedding,
        vector_store=vector_store,
        language_detection_service=language_detector,
        file_parser_service=file_parser,
        document_file_storage=file_storage,
    )
    _run(use_case.execute("img-1", "task-1"))

    # 無 override + KB 也未啟用切片 → 走原 auto_dispatch
    mock_ocr.ocr_page_auto_dispatch.assert_awaited_once()
    mock_ocr.ocr_page.assert_not_awaited()


def test_context_service_skipped_when_no_model_configured():
    """KB 沒設 context_model 且 caller 也沒 override → 應跳過 contextual block。"""
    context_service = AsyncMock()
    context_service.generate_contexts = AsyncMock()
    use_case, _ = _make_use_case(
        kb_context_model="",
        context_service=context_service,
        splitter_returns_chunks=True,
    )
    _run(use_case.execute("doc-1", "task-1"))

    context_service.generate_contexts.assert_not_awaited()
