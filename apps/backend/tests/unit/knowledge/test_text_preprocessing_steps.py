"""文字前處理 BDD Step Definitions"""

import unicodedata

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.knowledge.services import TextPreprocessor

scenarios("unit/knowledge/text_preprocessing.feature")


@pytest.fixture
def context():
    return {}


# --- Unicode NFC ---


@given("一段包含非 NFC 字元的文字")
def non_nfc_text(context):
    # U+00E9 (e-acute) can be represented as e + combining acute
    context["text"] = "caf\u0065\u0301"  # NFD form
    context["content_type"] = "text/plain"


@when("執行文字前處理")
def do_preprocess(context):
    context["result"] = TextPreprocessor.preprocess(
        context["text"], context["content_type"]
    )


@then("結果應為 NFC 正規化後的文字")
def verify_nfc(context):
    expected = unicodedata.normalize("NFC", context["text"])
    assert context["result"] == expected


# --- Whitespace collapse ---


@given("一段包含連續空白的文字")
def text_with_spaces(context):
    context["text"] = "hello   world\t\ttab   space"
    context["content_type"] = "text/plain"


@then("連續空白應折疊為單一空格")
def verify_whitespace_collapse(context):
    assert "   " not in context["result"]
    assert "\t" not in context["result"]
    assert "hello world tab space" == context["result"]


# --- Zero-width chars ---


@given("一段包含零寬字元的文字")
def text_with_zero_width(context):
    context["text"] = "hello\u200bworld\u200c\ufefftest"
    context["content_type"] = "text/plain"


@then("零寬字元應被移除")
def verify_zero_width_removed(context):
    assert "\u200b" not in context["result"]
    assert "\u200c" not in context["result"]
    assert "\ufeff" not in context["result"]
    assert context["result"] == "helloworldtest"


# --- Multi newline collapse ---


@given("一段包含超過兩個連續換行的文字")
def text_with_multi_newlines(context):
    context["text"] = "paragraph1\n\n\n\n\nparagraph2"
    context["content_type"] = "text/plain"


@then("連續換行應折疊為兩個")
def verify_newline_collapse(context):
    assert "\n\n\n" not in context["result"]
    assert "paragraph1\n\nparagraph2" == context["result"]


# --- PDF boilerplate ---


@given("一份多頁 PDF 文字且有重複頁首頁尾")
def pdf_with_boilerplate(context):
    header = "Company Confidential - Page Header"
    footer = "Copyright 2024 All Rights Reserved"
    pages = []
    for i in range(5):
        pages.append(f"{header}\nContent of page {i}\n{footer}")
    context["text"] = "\f".join(pages)
    context["content_type"] = "application/pdf"


@when("以 PDF content_type 執行文字前處理")
def do_pdf_preprocess(context):
    context["result"] = TextPreprocessor.preprocess(
        context["text"], context["content_type"]
    )


@then("重複出現的頁首頁尾應被移除")
def verify_boilerplate_removed(context):
    assert "Company Confidential" not in context["result"]
    assert "Copyright 2024" not in context["result"]
    assert "Content of page 0" in context["result"]
    assert "Content of page 4" in context["result"]
