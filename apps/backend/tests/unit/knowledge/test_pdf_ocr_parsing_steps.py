"""PDF OCR 解析 BDD Step Definitions"""

import asyncio
import io
from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.shared.exceptions import OcrProcessingError
from src.infrastructure.file_parser.ocr_engines.base import OcrEngine
from src.infrastructure.file_parser.ocr_file_parser_service import OcrFileParserService

scenarios("unit/knowledge/pdf_ocr_parsing.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_blank_pdf(num_pages: int) -> bytes:
    """Create a minimal PDF with N blank pages using pypdf."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_ocr_engine():
    engine = AsyncMock(spec=OcrEngine)
    engine.ocr_page = AsyncMock(return_value="OCR extracted text")
    return engine


# --- Given ---


@given("一個純圖像 PDF 的原始位元組（共 2 頁）")
def pdf_2_pages(context):
    context["raw_bytes"] = _make_blank_pdf(2)
    context["content_type"] = "application/pdf"
    context["expected_pages"] = 2


@given("一個純圖像 PDF 的原始位元組（共 1 頁）")
def pdf_1_page(context):
    context["raw_bytes"] = _make_blank_pdf(1)
    context["content_type"] = "application/pdf"
    context["expected_pages"] = 1


@given("一個純圖像 PDF 的原始位元組（共 0 頁）")
def pdf_0_pages(context):
    context["raw_bytes"] = _make_blank_pdf(0)
    context["content_type"] = "application/pdf"
    context["expected_pages"] = 0


@given(parsers.parse('一個 TXT 檔案內容為 "{content}"'))
def txt_file(context, content):
    context["raw_bytes"] = content.encode("utf-8")
    context["content_type"] = "text/plain"


@given("OCR 引擎已設定")
def ocr_engine_ready(context, mock_ocr_engine):
    context["ocr_engine"] = mock_ocr_engine


@given("OCR 引擎回傳錯誤")
def ocr_engine_error(context, mock_ocr_engine):
    mock_ocr_engine.ocr_page = AsyncMock(
        side_effect=OcrProcessingError("API error")
    )
    context["ocr_engine"] = mock_ocr_engine


# --- When ---


@when("解析該 PDF 檔案")
def parse_pdf(context):
    service = OcrFileParserService(ocr_engine=context["ocr_engine"])
    context["result"] = service.parse(
        context["raw_bytes"], context["content_type"]
    )


@when("嘗試解析該 PDF 檔案")
def try_parse_pdf(context):
    service = OcrFileParserService(ocr_engine=context["ocr_engine"])
    try:
        service.parse(context["raw_bytes"], context["content_type"])
        context["error"] = None
    except OcrProcessingError as e:
        context["error"] = e


@when("解析該檔案為 TXT 格式")
def parse_txt(context):
    service = OcrFileParserService(ocr_engine=context["ocr_engine"])
    context["result"] = service.parse(
        context["raw_bytes"], context["content_type"]
    )


# --- Then ---


@then("回傳包含每頁文字的純文字（以換頁符分隔）")
def verify_pages_joined(context):
    result = context["result"]
    pages = result.split("\f")
    assert len(pages) == context["expected_pages"]
    for page_text in pages:
        assert page_text == "OCR extracted text"


@then(parsers.parse("OCR 引擎被呼叫 {n:d} 次"))
def verify_ocr_call_count(context, n):
    assert context["ocr_engine"].ocr_page.call_count == n


@then("拋出 OcrProcessingError")
def verify_ocr_error(context):
    assert isinstance(context["error"], OcrProcessingError)


@then(parsers.parse('回傳純文字 "{expected}"'))
def verify_plain_text(context, expected):
    assert context["result"] == expected


@then("OCR 引擎未被呼叫")
def verify_ocr_not_called(context):
    context["ocr_engine"].ocr_page.assert_not_called()


@then("回傳空字串")
def verify_empty_string(context):
    assert context["result"] == ""
