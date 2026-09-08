"""Unit tests — 切片 OCR × 整頁 OCR 合併的純邏輯（Issue #82）。

``src/domain/knowledge/ocr_merge.py`` 無 I/O：解析 OCR 文字為
(頁面 markers, === 商品 blocks)、以正規化商品名為 block 身分、合併後
以同一文字格式重新輸出（下游 SeparatorTextSplitterService 不需改動）。
"""

from __future__ import annotations

import pytest

from src.domain.knowledge.ocr_merge import (
    UNKNOWN_VALUE,
    merge_hybrid_ocr_text,
    normalize_block_key,
    parse_ocr_text,
    render_ocr_text,
    same_block_identity,
)

_SLICED = """\
【頁面標題】不詳
【商家】不詳
【活動期間】不詳
【頁面級促銷說明】不詳
【頁面分類】商品頁

===
商品：木之薈樟腦油
品牌：木之薈
售價：199元/瓶
===

【頁面標題】不詳
【商家】家樂福
【活動期間】不詳
【頁面級促銷說明】不詳
【頁面分類】商品頁

===
商品：好米花蓮玉里有機米
售價：499元/包
===
"""

_FULL = """\
【頁面標題】TOP10 熱銷排行榜
【商家】家樂福
【活動期間】2026/04/08～2026/04/21
【頁面級促銷說明】不詳
【頁面分類】商品頁

===
商品：木之著樟腦油
品牌：木之著
售價：199元/瓶
===

===
商品：好米 花蓮玉里有機米
售價：499元/包
===

===
商品：艾瑪絲 森系列洗髮精系列
品牌：AROMASE
促銷：買一送一
===

===
商品：不詳
售價：99元
===
"""


# ── normalize_block_key ──


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("艾瑪絲 森系列洗髮精系列", "艾瑪絲森系列洗髮精系列"),
        ("艾瑪絲　森系列洗髮精系列", "艾瑪絲森系列洗髮精系列"),  # 全形空白
        ("Coca-Cola　350ml", "cocacola350ml"),
        ("ＡＲＯＭＡＳＥ", "aromase"),  # 全形英文 → 半形小寫
        ("好米（花蓮）玉里有機米!", "好米花蓮玉里有機米"),
        ("", ""),
        ("  ", ""),
    ],
)
def test_normalize_block_key(raw: str, expected: str):
    assert normalize_block_key(raw) == expected


# ── parse_ocr_text ──


def test_parse_extracts_markers_blocks_and_block_keys():
    page = parse_ocr_text(_FULL)
    assert [name for name, _ in page.markers] == [
        "頁面標題",
        "商家",
        "活動期間",
        "頁面級促銷說明",
        "頁面分類",
    ]
    assert dict(page.markers)["商家"] == "家樂福"
    assert dict(page.markers)["頁面級促銷說明"] == UNKNOWN_VALUE
    assert [b.name for b in page.blocks] == [
        "木之著樟腦油",
        "好米 花蓮玉里有機米",
        "艾瑪絲 森系列洗髮精系列",
        "不詳",
    ]
    assert page.blocks[2].key == "艾瑪絲森系列洗髮精系列"
    assert page.blocks[2].lines[1] == "品牌：AROMASE"


def test_parse_merges_repeated_tile_markers_preferring_known_values():
    """切片輸出每 tile 各帶一組 markers；同名只留一個，值取第一個非「不詳」。"""
    page = parse_ocr_text(_SLICED)
    names = [name for name, _ in page.markers]
    assert names.count("商家") == 1
    assert dict(page.markers)["商家"] == "家樂福"
    assert dict(page.markers)["頁面標題"] == UNKNOWN_VALUE
    assert [b.name for b in page.blocks] == ["木之薈樟腦油", "好米花蓮玉里有機米"]


def test_parse_tolerates_unclosed_trailing_block():
    text = "【商家】家樂福\n\n===\n商品：可口可樂\n售價：25元/瓶"
    page = parse_ocr_text(text)
    assert [b.name for b in page.blocks] == ["可口可樂"]


def test_parse_unstructured_text_has_no_blocks_and_keeps_loose_lines():
    page = parse_ocr_text("第一行文字\n第二行文字\n")
    assert page.blocks == []
    assert page.markers == []
    assert page.loose_lines == ["第一行文字", "第二行文字"]


def test_parse_keeps_loose_lines_outside_blocks():
    text = "【商家】家樂福\n備註：全店適用\n\n===\n商品：A\n===\n"
    page = parse_ocr_text(text)
    assert page.loose_lines == ["備註：全店適用"]
    assert [b.name for b in page.blocks] == ["A"]


# ── render_ocr_text ──


def test_render_round_trip_is_stable():
    rendered = render_ocr_text(parse_ocr_text(_FULL))
    assert rendered == render_ocr_text(parse_ocr_text(rendered))
    assert rendered.startswith("【頁面標題】TOP10 熱銷排行榜\n【商家】家樂福\n")
    # blocks 以 === 包住、block 之間空一行（與 _CATALOG_PROMPT 範例一致）
    block = "===\n商品：木之著樟腦油\n品牌：木之著\n售價：199元/瓶\n===\n\n==="
    assert block in rendered
    assert rendered.endswith("===\n")


# ── merge_hybrid_ocr_text ──


def test_merge_adds_block_missing_from_slices_exactly_once():
    merged = merge_hybrid_ocr_text(_SLICED, _FULL)
    assert merged.count("商品：艾瑪絲 森系列洗髮精系列") == 1
    assert "品牌：AROMASE" in merged


def test_merge_keeps_slice_version_for_shared_blocks():
    merged = merge_hybrid_ocr_text(_SLICED, _FULL)
    assert "商品：木之薈樟腦油" in merged
    assert "木之著" not in merged
    # 名稱正規化後相同（空白差異）→ 視為同一 block，不重複
    assert merged.count("好米") == 1
    assert "商品：好米花蓮玉里有機米" in merged


def test_merge_fills_unknown_page_markers_from_full_page():
    merged = merge_hybrid_ocr_text(_SLICED, _FULL)
    assert "【頁面標題】TOP10 熱銷排行榜" in merged
    assert "【活動期間】2026/04/08～2026/04/21" in merged
    assert "【頁面標題】不詳" not in merged
    # 兩邊都不詳 → 維持不詳，且 marker 不省略
    assert merged.count("【頁面級促銷說明】不詳") == 1
    # 切片已知的值優先（切片 商家 = 家樂福）
    assert merged.count("【商家】家樂福") == 1
    assert merged.count("【頁面分類】商品頁") == 1


def test_merge_keeps_sliced_marker_when_full_page_disagrees():
    sliced = "【商家】全聯\n\n===\n商品：A\n===\n"
    full = "【商家】家樂福\n\n===\n商品：A\n===\n"
    merged = merge_hybrid_ocr_text(sliced, full)
    assert "【商家】全聯" in merged
    assert "家樂福" not in merged


def test_merge_skips_full_page_blocks_without_identity():
    """整頁的「商品：不詳」block 無法判斷是否重複 → 不補進來。"""
    merged = merge_hybrid_ocr_text(_SLICED, _FULL)
    assert "商品：不詳" not in merged
    assert "售價：99元" not in merged


def test_merge_block_order_is_sliced_first_then_additions():
    merged = merge_hybrid_ocr_text(_SLICED, _FULL)
    assert merged.index("木之薈樟腦油") < merged.index("好米花蓮玉里有機米")
    assert merged.index("好米花蓮玉里有機米") < merged.index("艾瑪絲")


def test_merge_with_empty_sliced_output_takes_all_identified_full_blocks():
    merged = merge_hybrid_ocr_text("", _FULL)
    assert merged.count("===") == 6  # 3 blocks × 2（不詳 block 不補）
    assert "【商家】家樂福" in merged


def test_merge_with_empty_full_output_returns_sliced_structure():
    merged = merge_hybrid_ocr_text(_SLICED, "")
    assert "商品：木之薈樟腦油" in merged
    assert "商品：好米花蓮玉里有機米" in merged
    assert merged.count("【商家】家樂福") == 1


def test_merge_unstructured_text_returns_sliced_unchanged():
    """兩邊都沒有 === block 也沒有 marker（general prompt）→ 不動切片結果。"""
    sliced = "tile 1 text\n\ntile 2 text"
    assert merge_hybrid_ocr_text(sliced, "full page text") == sliced


def test_merge_preserves_loose_lines_from_sliced_output():
    sliced = "【商家】家樂福\n附註：僅限門市\n\n===\n商品：A\n===\n"
    full = "【商家】家樂福\n\n===\n商品：B\n===\n"
    merged = merge_hybrid_ocr_text(sliced, full)
    assert "附註：僅限門市" in merged
    assert "商品：A" in merged and "商品：B" in merged


def test_merge_output_is_splittable_by_separator_splitter():
    """合併輸出格式必須讓 SeparatorTextSplitterService 原樣切出每個 block。"""
    from src.infrastructure.text_splitter.separator_text_splitter_service import (
        SeparatorTextSplitterService,
    )

    merged = merge_hybrid_ocr_text(_SLICED, _FULL)
    chunks = SeparatorTextSplitterService().split(merged, "doc-1", "t-1")
    names = [c.content.splitlines()[0] for c in chunks]
    assert names == [
        "商品：木之薈樟腦油",
        "商品：好米花蓮玉里有機米",
        "商品：艾瑪絲 森系列洗髮精系列",
    ]
    assert all("家樂福" in c.context_text for c in chunks)


# ── same_block_identity（字形容錯 vs 規格變體）──


def test_same_block_identity_tolerates_single_glyph_ocr_difference():
    assert same_block_identity(
        normalize_block_key("木之薈樟腦油"), normalize_block_key("木之著樟腦油")
    )


def test_same_block_identity_distinguishes_size_variants():
    assert not same_block_identity(
        normalize_block_key("可口可樂 350ml"), normalize_block_key("可口可樂 600ml")
    )


def test_same_block_identity_rejects_empty_keys():
    assert not same_block_identity("", "abc")
    assert not same_block_identity("abc", "")


def test_merge_adds_size_variant_only_seen_by_full_page():
    sliced = "===\n商品：可口可樂 350ml\n售價：25元\n===\n"
    full = (
        "===\n商品：可口可樂 350ml\n售價：25元\n===\n\n"
        "===\n商品：可口可樂 600ml\n售價：35元\n===\n"
    )
    merged = merge_hybrid_ocr_text(sliced, full)
    assert merged.count("商品：可口可樂") == 2
    assert "600ml" in merged


def test_promo_marker_accumulates_distinct_fragments_across_tiles_and_full_page():
    """20 題 C5 回歸：切片與整頁各看到活動的一部分，合併後兩段都要在。"""
    from src.domain.knowledge.ocr_merge import merge_hybrid_ocr_text

    sliced = (
        "【頁面級促銷說明】單筆最高贈50點電子貼紙，需下載APP，大宗採購不適用\n"
        "【頁面分類】商品頁\n\n===\n商品：A\n售價：1元\n===\n"
        "【頁面級促銷說明】單筆最高贈50點電子貼紙，需下載APP，大宗採購不適用\n"
    )
    full = (
        "【頁面標題】單一商品每滿100元加贈1點電子貼紙\n"
        "【頁面級促銷說明】單一商品每滿100元加贈1點（同價位同系列可混搭）\n"
        "【頁面分類】商品頁\n\n===\n商品：A\n售價：1元\n===\n"
    )
    merged = merge_hybrid_ocr_text(sliced, full)
    promo = [ln for ln in merged.splitlines() if ln.startswith("【頁面級促銷說明】")]
    assert len(promo) == 1
    assert "最高贈50點" in promo[0] and "每滿100元加贈1點" in promo[0]
    assert promo[0].count("最高贈50點") == 1
    assert "【頁面標題】單一商品每滿100元加贈1點電子貼紙" in merged

