"""查詢文字正規化 — 中文異體字與全形字統一（POC 問題 6）。

純向量檢索對異體字敏感（「週年慶」vs OCR chunk 的「周年慶」）。
檢索前把 query 正規化到知識庫常見字形：只影響 embedding 輸入，
不改使用者原文、不影響回覆內容。

正規化方向以「知識庫實際字形」為準（OCR 與 FAQ 慣用簡體部件字形），
新增對映前先確認庫內用字，避免反向正規化拉低相似度。
"""
from __future__ import annotations

import unicodedata

# 異體字對映：query 字形 → 知識庫慣用字形
_VARIANT_MAP = str.maketrans(
    {
        "週": "周",  # 週年慶 → 周年慶（DM OCR 慣用）
        "臺": "台",  # 臺北 → 台北
    }
)


def normalize_query_variants(text: str) -> str:
    """NFKC（全形→半形）+ 異體字統一。純函式，無副作用。"""
    return unicodedata.normalize("NFKC", text).translate(_VARIANT_MAP)
