"""Separator-Based Chunking BDD Step Definitions"""

from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.text_splitter.separator_text_splitter_service import (
    SeparatorTextSplitterService,
)

scenarios("unit/knowledge/separator_chunking.feature")


@pytest.fixture
def ctx():
    return {}


def _make_splitter(with_fallback: bool = True) -> tuple[SeparatorTextSplitterService, MagicMock | None]:
    fallback = MagicMock() if with_fallback else None
    if fallback is not None:
        fallback.split.return_value = [MagicMock(content="fallback-chunk")]
    return SeparatorTextSplitterService(fallback=fallback), fallback


@given(
    parsers.parse(
        "OCR 文本含【商家】全聯與【頁面分類】商品頁與 {count:d} 個 === 分隔的商品區塊"
    )
)
def catalog_text_with_header_and_products(ctx, count):
    blocks = "\n\n".join(
        f"===\n商品：商品_{i}\n品牌：品牌_{i}\n售價：{(i+1)*99}元/組\n==="
        for i in range(count)
    )
    text = "【商家】全聯\n【頁面分類】商品頁\n\n" + blocks
    splitter, fallback = _make_splitter()
    ctx["text"] = text
    ctx["expected_count"] = count
    ctx["splitter"] = splitter
    ctx["fallback"] = fallback


@given(
    parsers.parse(
        "OCR 文本含 {count:d} 個商品區塊與尾部頁面級促銷說明 {promo}"
    )
)
def catalog_text_with_footer_promo(ctx, count, promo):
    blocks = "\n\n".join(
        f"===\n商品：商品_{i}\n售價：{(i+1)*50}元\n==="
        for i in range(count)
    )
    text = blocks + f"\n\n【頁面級促銷說明】\n- {promo}\n"
    splitter, fallback = _make_splitter()
    ctx["text"] = text
    ctx["expected_count"] = count
    ctx["splitter"] = splitter
    ctx["fallback"] = fallback


@given("OCR 文本為一般段落無分隔符")
def plain_text_no_separator(ctx):
    text = "這是一段普通的文件內容，描述某個商品的特性，但沒有使用 === 分隔符也沒有商品結構。"
    splitter, fallback = _make_splitter()
    ctx["text"] = text
    ctx["splitter"] = splitter
    ctx["fallback"] = fallback


@given("OCR 文本只有【商家】markers 但無 === 分隔符")
def text_with_markers_no_separator(ctx):
    text = "【商家】家樂福\n【頁面分類】資訊頁\n\n本頁說明會員權益但無商品列表。"
    splitter, fallback = _make_splitter()
    ctx["text"] = text
    ctx["splitter"] = splitter
    ctx["fallback"] = fallback


@given(
    parsers.parse(
        "OCR 文本含【商家】家樂福與【活動期間】2026/04/08～2026/04/30 與 "
        "{count:d} 個 === 分隔的活動條目"
    )
)
def promotion_text_with_activities(ctx, count):
    blocks = "\n\n".join(
        f"===\n活動：活動_{i}\n優惠對象：家樂福會員\n優惠條件：滿 {(i+1)*100} 元享 {(i+1)*5}% 回饋\n==="
        for i in range(count)
    )
    text = (
        "【商家】家樂福\n"
        "【活動主題】中國信託 unipen 聯名卡\n"
        "【活動期間】2026/04/08～2026/04/30\n\n"
        + blocks
    )
    splitter, fallback = _make_splitter()
    ctx["text"] = text
    ctx["expected_count"] = count
    ctx["splitter"] = splitter
    ctx["fallback"] = fallback


@given(
    parsers.parse(
        "OCR 文本含【商家】家樂福與【活動期間】2026/04/08～2026/04/30 與 "
        "{products:d} 個商品區塊與 {activities:d} 個活動條目"
    )
)
def mixed_text_with_products_and_activities(ctx, products, activities):
    product_blocks = "\n\n".join(
        f"===\n商品：商品_{i}\n品牌：品牌_{i}\n售價：{(i+1)*99}元\n==="
        for i in range(products)
    )
    activity_blocks = "\n\n".join(
        f"===\n活動：活動_{i}\n優惠條件：滿 {(i+1)*200} 元現折 {(i+1)*5}%\n==="
        for i in range(activities)
    )
    text = (
        "【商家】家樂福\n"
        "【活動期間】2026/04/08～2026/04/30\n\n"
        "## 商品段\n\n"
        + product_blocks
        + "\n\n## 活動段\n\n"
        + activity_blocks
    )
    splitter, fallback = _make_splitter()
    ctx["text"] = text
    ctx["expected_count"] = products + activities
    ctx["splitter"] = splitter
    ctx["fallback"] = fallback


@when("我用 separator splitter 切塊")
def do_separator_split(ctx):
    ctx["chunks"] = ctx["splitter"].split(
        ctx["text"],
        "doc-sep",
        "tenant-sep",
        content_type="application/pdf",
    )


@then(parsers.parse("應產生 {count:d} 個 chunks"))
def assert_chunk_count(ctx, count):
    assert len(ctx["chunks"]) == count


@then("每個 chunk 的 content 應對應一個商品區塊")
def assert_each_chunk_has_one_product(ctx):
    for chunk in ctx["chunks"]:
        # Each chunk content should contain exactly one 商品： line
        product_count = chunk.content.count("商品：")
        assert product_count == 1, (
            f"Expected 1 product per chunk, got {product_count} in: {chunk.content[:100]}"
        )


@then(parsers.parse("每個 chunk 的 context_text 應包含「{keyword}」"))
def assert_context_text_contains(ctx, keyword):
    for chunk in ctx["chunks"]:
        assert keyword in chunk.context_text, (
            f"Expected '{keyword}' in context_text, got: {chunk.context_text!r}"
        )


@then("應呼叫 fallback splitter 切塊")
def assert_fallback_called(ctx):
    ctx["fallback"].split.assert_called_once()
