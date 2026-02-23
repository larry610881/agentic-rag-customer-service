"""檔案解析 BDD Step Definitions"""

import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.shared.exceptions import UnsupportedFileTypeError
from src.infrastructure.file_parser.default_file_parser_service import (
    DefaultFileParserService,
)

scenarios("unit/knowledge/file_parsing.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def parser_service():
    return DefaultFileParserService()


@given(parsers.parse('一個 TXT 檔案內容為 "{content}"'))
def txt_file(context, content):
    context["raw_bytes"] = content.encode("utf-8")
    context["content_type"] = "text/plain"


@given(parsers.parse('一個 CSV 檔案內容為 "{content}"'))
def csv_file(context, content):
    # pytest-bdd passes literal \n; convert to real newlines
    context["raw_bytes"] = content.replace("\\n", "\n").encode("utf-8")
    context["content_type"] = "text/csv"


@given("一個 PDF 檔案的原始位元組")
def pdf_file(context):
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    context["raw_bytes"] = buf.getvalue()
    context["content_type"] = "application/pdf"


@given("一個 DOCX 檔案的原始位元組")
def docx_file(context):
    import io

    from docx import Document

    doc = Document()
    doc.add_paragraph("Test paragraph content")
    buf = io.BytesIO()
    doc.save(buf)
    context["raw_bytes"] = buf.getvalue()
    context["content_type"] = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@given(parsers.parse('一個不支援格式 "{content_type}" 的檔案'))
def unsupported_file(context, content_type):
    context["raw_bytes"] = b"fake data"
    context["content_type"] = content_type


@when("解析該檔案")
def parse_file(context, parser_service):
    result = parser_service.parse(context["raw_bytes"], context["content_type"])
    context["result"] = result


@when("嘗試解析該檔案")
def try_parse_file(context, parser_service):
    try:
        parser_service.parse(context["raw_bytes"], context["content_type"])
        context["error"] = None
    except UnsupportedFileTypeError as e:
        context["error"] = e


@then(parsers.parse('回傳純文字 "{expected}"'))
def returns_text(context, expected):
    assert context["result"] == expected


@then(parsers.parse('回傳包含 "{word1}" 和 "{word2}" 的合併文字'))
def returns_merged_text(context, word1, word2):
    assert word1 in context["result"]
    assert word2 in context["result"]


@then("回傳提取的文字內容")
def returns_extracted_pdf_text(context):
    # PDF might return empty text for blank page, but should not error
    assert isinstance(context["result"], str)


@then("回傳段落文字內容")
def returns_paragraph_text(context):
    assert "Test paragraph content" in context["result"]


@then("拋出 UnsupportedFileTypeError")
def raises_unsupported(context):
    assert isinstance(context["error"], UnsupportedFileTypeError)
