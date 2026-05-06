"""Page-type auto-dispatch OCR routing — unit tests.

Verifies:
- 4 page-type prompts loaded in _PAGE_TYPE_PROMPTS
- classify_page_type returns valid token / falls back to catalog
- ocr_page_auto_dispatch dispatches to correct prompt + injects 偵測類型 marker
- OcrFileParserService routes ocr_mode="auto" → ocr_page_auto_dispatch path
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.file_parser.ocr_engines.claude_vision_ocr import (
    _PAGE_TYPE_PROMPTS,
    _VALID_PAGE_TYPES,
    OCR_PROMPTS,
    ClaudeVisionOcrEngine,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_engine_with_fake_client(
    classify_response: str = "catalog",
    ocr_response: str = "(ocr text)",
) -> ClaudeVisionOcrEngine:
    """Build engine with mocked Anthropic client returning canned responses."""
    engine = ClaudeVisionOcrEngine.__new__(ClaudeVisionOcrEngine)
    engine._api_key = "test-key"
    engine._api_key_resolver = None
    engine._model = "fake-haiku"
    engine._semaphore = asyncio.Semaphore(5)
    engine.last_input_tokens = 0
    engine.last_output_tokens = 0

    fake_client = MagicMock()
    # call_state lets us return classify result first, then OCR result
    call_state = {"calls": 0}

    async def fake_create(**kwargs):
        prompts = kwargs.get("messages", [{}])[0].get("content", [])
        text_block = next(
            (b for b in prompts if b.get("type") == "text"), None
        )
        prompt_text = text_block.get("text", "") if text_block else ""
        usage = MagicMock(input_tokens=10, output_tokens=5)
        msg = MagicMock(usage=usage)
        # Return classify response if prompt is the classify prompt
        if "請分類為下列其中一種" in prompt_text:
            msg.content = [MagicMock(text=classify_response)]
        else:
            msg.content = [MagicMock(text=ocr_response)]
        call_state["calls"] += 1
        return msg

    fake_client.messages = MagicMock()
    fake_client.messages.create = fake_create
    engine._client = fake_client
    engine._fake_call_state = call_state  # type: ignore[attr-defined]
    return engine


# ── prompt registry ─────────────────────────────────────────


def test_page_type_prompts_has_four_types():
    assert _VALID_PAGE_TYPES == frozenset(
        {"catalog", "promotion", "mixed", "cover"}
    )
    assert all(p.strip() for p in _PAGE_TYPE_PROMPTS.values()), (
        "no empty prompt allowed"
    )


def test_ocr_prompts_dict_contains_general_and_catalog_only():
    """auto mode 不對應靜態 prompt — 走 ocr_page_auto_dispatch。"""
    assert "general" in OCR_PROMPTS
    assert "catalog" in OCR_PROMPTS
    assert "auto" not in OCR_PROMPTS


def test_promotion_prompt_targets_credit_card_pages():
    text = _PAGE_TYPE_PROMPTS["promotion"]
    # Critical fields user 在 LINE 問問題時最常用
    assert "活動主題" in text
    assert "活動期間" in text
    assert "優惠條件" in text
    assert "優惠對象" in text


def test_mixed_prompt_has_both_sections():
    text = _PAGE_TYPE_PROMPTS["mixed"]
    assert "## 商品段" in text
    assert "## 活動段" in text


# ── classify_page_type ─────────────────────────────────────


def test_classify_returns_valid_token():
    engine = _make_engine_with_fake_client(classify_response="promotion")
    page_type = _run(engine.classify_page_type(b"\x89PNG\r\nfake"))
    assert page_type == "promotion"


def test_classify_strips_whitespace_and_punctuation():
    engine = _make_engine_with_fake_client(classify_response="  catalog.\n")
    page_type = _run(engine.classify_page_type(b"\x89PNG\r\nfake"))
    assert page_type == "catalog"


def test_classify_falls_back_to_catalog_on_invalid_response():
    engine = _make_engine_with_fake_client(classify_response="weird_garbage")
    page_type = _run(engine.classify_page_type(b"\x89PNG\r\nfake"))
    assert page_type == "catalog"


def test_classify_handles_multi_token_response():
    """LLM 多嘴回 'promotion - 信用卡頁' → 取第一個 token。"""
    engine = _make_engine_with_fake_client(
        classify_response="promotion - 這是信用卡頁"
    )
    page_type = _run(engine.classify_page_type(b"\x89PNG\r\nfake"))
    assert page_type == "promotion"


# ── ocr_page_auto_dispatch ─────────────────────────────────


def test_auto_dispatch_returns_page_type_and_text():
    engine = _make_engine_with_fake_client(
        classify_response="promotion",
        ocr_response="【活動主題】中國信託聯名卡\n【活動期間】2026/04/01～2026/04/30",
    )
    page_type, text = _run(engine.ocr_page_auto_dispatch(b"\x89PNG\r\nfake"))
    assert page_type == "promotion"
    assert text.startswith("【偵測類型】promotion\n")
    assert "中國信託聯名卡" in text


def test_auto_dispatch_uses_two_api_calls_classify_then_ocr():
    engine = _make_engine_with_fake_client(
        classify_response="catalog",
        ocr_response="===\n商品: X\n===",
    )
    _run(engine.ocr_page_auto_dispatch(b"\x89PNG\r\nfake"))
    # 1 classify + 1 ocr = 2 calls
    assert engine._fake_call_state["calls"] == 2


# ── OcrFileParserService routing ─────────────────────────


def test_parse_pdf_async_auto_mode_calls_auto_dispatch():
    from src.infrastructure.file_parser.ocr_file_parser_service import (
        OcrFileParserService,
    )

    fake_engine = MagicMock()
    fake_engine.last_input_tokens = 0
    fake_engine.last_output_tokens = 0
    fake_engine.ocr_page_auto_dispatch = AsyncMock(
        return_value=("promotion", "【偵測類型】promotion\n(text)")
    )
    fake_engine.ocr_page = AsyncMock(
        side_effect=AssertionError("auto mode 不該走 ocr_page")
    )

    svc = OcrFileParserService.__new__(OcrFileParserService)
    svc._ocr = fake_engine
    svc._default = MagicMock()
    svc.last_input_tokens = 0
    svc.last_output_tokens = 0
    svc.last_model = ""

    # Bypass real PDF rasterize — patch extract_pages_as_images
    fake_pdf = b"%PDF-fake"
    from src.infrastructure.file_parser import ocr_file_parser_service as mod
    real_extract = mod.extract_pages_as_images
    try:
        mod.extract_pages_as_images = MagicMock(
            return_value=[b"page1-img", b"page2-img"]
        )
        result = _run(svc.parse_pdf_async(fake_pdf, ocr_mode="auto"))
    finally:
        mod.extract_pages_as_images = real_extract

    assert "promotion" in result
    assert fake_engine.ocr_page_auto_dispatch.await_count == 2


def test_parse_pdf_async_catalog_mode_keeps_existing_path():
    """既有 catalog 模式行為 0 改變 — 仍走 ocr_page(prompt=...)."""
    from src.infrastructure.file_parser.ocr_file_parser_service import (
        OcrFileParserService,
    )

    fake_engine = MagicMock()
    fake_engine.last_input_tokens = 0
    fake_engine.last_output_tokens = 0
    fake_engine.ocr_page = AsyncMock(return_value="(catalog text)")
    fake_engine.ocr_page_auto_dispatch = AsyncMock(
        side_effect=AssertionError("catalog mode 不該走 auto_dispatch")
    )

    svc = OcrFileParserService.__new__(OcrFileParserService)
    svc._ocr = fake_engine
    svc._default = MagicMock()
    svc.last_input_tokens = 0
    svc.last_output_tokens = 0
    svc.last_model = ""

    from src.infrastructure.file_parser import ocr_file_parser_service as mod
    real_extract = mod.extract_pages_as_images
    try:
        mod.extract_pages_as_images = MagicMock(return_value=[b"img"])
        _run(svc.parse_pdf_async(b"%PDF-fake", ocr_mode="catalog"))
    finally:
        mod.extract_pages_as_images = real_extract

    assert fake_engine.ocr_page.await_count == 1
