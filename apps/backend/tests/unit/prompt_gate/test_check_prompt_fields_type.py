"""Regression: check_prompt_fields 非字串值回 StaticCheckFailedError 非 500（M1）。"""

import pytest

from src.application.prompt_gate.static_checks import (
    StaticCheckFailedError,
    check_prompt_fields,
)


def test_non_string_value_raises_static_check_not_typeerror():
    with pytest.raises(StaticCheckFailedError) as exc:
        check_prompt_fields({"bot_prompt": 123})  # type: ignore[dict-item]
    assert any(v.type == "invalid_type" for v in exc.value.violations)


def test_none_value_is_ok():
    check_prompt_fields({"bot_prompt": None})  # type: ignore[dict-item]  # no raise


def test_valid_string_still_checked():
    # 正常字串仍走原檢查（無違規 → 不 raise）
    check_prompt_fields({"bot_prompt": "你是客服"})
