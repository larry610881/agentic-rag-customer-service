"""Regression: OCR 結構化 prompt 必須含 _OCR_DISCIPLINE 防 hallucinate 段。

過去 _CATALOG_PROMPT 沒有強調「逐字準確 / 不要編造 / 罕用字仔細辨認」
→ LLM 把「樟腦油」hallucinate 成「橙醬油/橙甜油/橙醛油」
→ 「薈」hallucinate 成「香/著/奢」這類字形不像但語意接近的常見字。

此測試保證 4 個結構化 prompt 都注入紀律段，未來若有人意外移除會被擋下。
"""

from __future__ import annotations

import pytest

from src.infrastructure.file_parser.ocr_engines.claude_vision_ocr import (
    _CATALOG_PROMPT,
    _COVER_PROMPT,
    _MIXED_PROMPT,
    _OCR_DISCIPLINE,
    _PROMOTION_PROMPT,
)


@pytest.mark.parametrize(
    "name,prompt",
    [
        ("catalog", _CATALOG_PROMPT),
        ("promotion", _PROMOTION_PROMPT),
        ("mixed", _MIXED_PROMPT),
        ("cover", _COVER_PROMPT),
    ],
)
def test_structured_prompt_contains_ocr_discipline(name: str, prompt: str):
    assert _OCR_DISCIPLINE in prompt, (
        f"{name} prompt 缺失 _OCR_DISCIPLINE 段 — 會回歸到 hallucinate 問題"
    )


def test_discipline_mentions_rare_char_protection():
    """紀律段必須明確指示罕用字保護（薈/樟腦/萃/茅 case）。"""
    assert "罕用字" in _OCR_DISCIPLINE
    assert "薈" in _OCR_DISCIPLINE or "樟腦" in _OCR_DISCIPLINE


def test_discipline_forbids_hallucination():
    """紀律段必須明示「不要編造」。"""
    assert "不要編造" in _OCR_DISCIPLINE or "不要硬猜" in _OCR_DISCIPLINE


def test_discipline_provides_uncertainty_escape():
    """紀律段必須提供「不確定」的逃生口（[模糊:???]）。"""
    assert "[模糊:???]" in _OCR_DISCIPLINE or "模糊" in _OCR_DISCIPLINE
