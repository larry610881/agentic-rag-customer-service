"""查詢異體字正規化測試（POC 問題 6 — 週年慶 vs 周年慶）。

純向量檢索對中文異體字敏感：使用者輸入「週年慶」、OCR chunk 寫
「周年慶」時相似度被拉低。檢索前把 query 正規化到常見 OCR 慣用字形，
只影響 embedding 輸入，不改使用者原文。
"""
from src.domain.rag.text_normalization import normalize_query_variants


def test_zhou_variant_normalized():
    result = normalize_query_variants("家速配週年慶有什麼活動")
    assert result == "家速配周年慶有什麼活動"


def test_tai_variant_normalized():
    assert normalize_query_variants("臺北店營業時間") == "台北店營業時間"


def test_fullwidth_chars_normalized():
    """全形英數字 → 半形（NFKC），利於商品型號/數字比對。"""
    assert normalize_query_variants("ＶＩＰ會員　滿１０萬") == "VIP會員 滿10萬"


def test_plain_text_unchanged():
    text = "包大人尿布有優惠嗎"
    assert normalize_query_variants(text) == text


def test_empty_string():
    assert normalize_query_variants("") == ""
