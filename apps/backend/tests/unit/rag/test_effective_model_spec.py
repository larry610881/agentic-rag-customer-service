"""Regression: rewrite/HyDE 模型 spec 空白字元退回預設（H17 後端防禦層）。"""

import pytest

from src.application.rag._query_rewriter import effective_model_spec

_DEFAULT = "anthropic:claude-haiku-4-5"


@pytest.mark.parametrize("value", ["", " ", "  ", None, "\t"])
def test_blank_falls_back_to_default(value):
    # 前端「（預設）」曾存成單一空白 " " → 必須退回預設，而非當 model spec
    assert effective_model_spec(value) == _DEFAULT


@pytest.mark.parametrize("value", ["openai:gpt-4o", "anthropic:claude-opus"])
def test_real_spec_preserved(value):
    assert effective_model_spec(value) == value


def test_surrounding_whitespace_trimmed():
    assert effective_model_spec("  openai:gpt-4o  ") == "openai:gpt-4o"
