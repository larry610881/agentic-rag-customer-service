"""Regression test for hotfix 9349651.

ReprocessDocumentUseCase 對 image/* 必須走 ocr_engine.ocr_page()
而非 file_parser.parse()。

之前 PDF 子頁 (content_type='image/png') reprocess 永遠失敗：
    Unsupported file type: 'image/png'

根因：reprocess pipeline 跟 process pipeline 不對齊
（process 有 image OCR 分支，reprocess 沒有）

此檔保證未來再回歸時測試會 fail。
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
    # 用 new_event_loop 而非 get_event_loop 避免測試間 event loop pollution
    # （previous test left running tasks on shared loop → InvalidStateError 等）
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_use_case(file_parser_mock):
    """建立 ReprocessDocumentUseCase + 各種 mocked deps。"""
    doc_repo = AsyncMock()
    doc_repo.find_by_id = AsyncMock(
        return_value=Document(
            id=DocumentId(value="img-doc-1"),
            kb_id="kb-1",
            tenant_id="t-1",
            filename="page_010.png",
            content_type="image/png",  # ← 關鍵：PDF 子頁
            content="",
            raw_content=b"\x89PNG_FAKE_BYTES",  # 直接走 BYTEA 路徑簡化測試
            storage_path="",
        )
    )
    doc_repo.update_status = AsyncMock()
    doc_repo.update_content = AsyncMock()
    doc_repo.update_quality = AsyncMock()
    doc_repo.delete_chunks_by_document = AsyncMock()
    doc_repo.bulk_save_chunks = AsyncMock()

    task_repo = AsyncMock()
    task_repo.update_status = AsyncMock()

    kb_repo = AsyncMock()
    kb_repo.find_by_id = AsyncMock(
        return_value=KnowledgeBase(ocr_mode="catalog")
    )

    splitter = MagicMock()
    splitter.split.return_value = []

    embedding = AsyncMock()
    embedding.embed_documents = AsyncMock(return_value=[])
    vector_store = AsyncMock()
    vector_store.ensure_collection = AsyncMock()
    vector_store.upsert = AsyncMock()
    vector_store.delete = AsyncMock()
    language_detector = MagicMock()
    language_detector.detect.return_value = "zh"
    file_storage = AsyncMock()
    file_storage.load = AsyncMock(side_effect=FileNotFoundError)

    return ReprocessDocumentUseCase(
        document_repository=doc_repo,
        processing_task_repository=task_repo,
        knowledge_base_repository=kb_repo,
        text_splitter_service=splitter,
        embedding_service=embedding,
        vector_store=vector_store,
        language_detection_service=language_detector,
        file_parser_service=file_parser_mock,
        document_file_storage=file_storage,
    ), doc_repo


def test_reprocess_image_png_calls_ocr_engine_not_file_parser_parse():
    """關鍵 regression：image/png 必須走 _ocr.ocr_page()，禁止呼叫 .parse()。"""
    # 模擬 file_parser 內部有 _ocr engine（catalog 模式真實設置）
    mock_ocr = AsyncMock()
    mock_ocr.ocr_page = AsyncMock(return_value="OCR result text from image")
    file_parser = MagicMock()
    file_parser._ocr = mock_ocr
    # parse 也存在但不應被呼叫；若被呼叫就 fail（模擬之前 bug 的情境）
    file_parser.parse = MagicMock(
        side_effect=ValueError("Unsupported file type: 'image/png'")
    )

    use_case, _ = _make_use_case(file_parser)
    _run(use_case.execute("img-doc-1", "task-1"))

    # ✅ 應呼叫 OCR engine
    mock_ocr.ocr_page.assert_awaited_once()
    # ❌ 絕不應呼叫 file_parser.parse（image/png 不支援會炸）
    file_parser.parse.assert_not_called()


def test_reprocess_image_png_uses_kb_ocr_mode_for_prompt():
    """OCR prompt 應根據 KB.ocr_mode 選擇（catalog → 賣場 DM prompt）。"""
    mock_ocr = AsyncMock()
    mock_ocr.ocr_page = AsyncMock(return_value="text")
    file_parser = MagicMock()
    file_parser._ocr = mock_ocr
    file_parser.parse = MagicMock()

    use_case, _ = _make_use_case(file_parser)
    _run(use_case.execute("img-doc-1", "task-1"))

    # ocr_page 收到 (raw_content, prompt=...) — prompt 不應為空
    call_kwargs = mock_ocr.ocr_page.call_args.kwargs
    assert "prompt" in call_kwargs
    assert call_kwargs["prompt"]  # 非空字串


def test_reprocess_image_without_ocr_engine_falls_through_to_parse():
    """若 file_parser 沒有 _ocr attribute（極端 edge case），走 parse fallback。"""
    file_parser = MagicMock(spec=["parse"])  # 顯式不給 _ocr
    file_parser.parse = MagicMock(return_value="parsed text")

    use_case, _ = _make_use_case(file_parser)
    # 此情況預期 .parse() 被呼叫（即使會炸也是 file_parser 自己的事）
    # 用 try/except 覆蓋 — 至少證明 fallback path 存在
    try:
        _run(use_case.execute("img-doc-1", "task-1"))
    except Exception:
        pass

    # 重點：當沒有 _ocr 時，code 真的有 fallback 到 parse — 表示分支邏輯正確
    file_parser.parse.assert_called()
