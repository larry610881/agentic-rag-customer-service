"""Regression: CLI target_field → level 對映（H15）。

原本 base_prompt 被映到 system 層 → (system, base_prompt) 不在 _TARGET_MAP →
所有以 base_prompt 為 target 的內建 dataset 一開跑即 ValueError。
"""

import pytest

from prompt_optimizer.__main__ import resolve_target_level
from prompt_optimizer.db_client import _TARGET_MAP


@pytest.mark.parametrize(
    "field,expected_level",
    [
        ("base_prompt", "bot"),
        ("bot_prompt", "bot"),
        ("system_prompt", "system"),
    ],
)
def test_resolve_target_level(field, expected_level):
    assert resolve_target_level(field) == expected_level


@pytest.mark.parametrize("field", ["base_prompt", "bot_prompt", "system_prompt"])
def test_resolved_target_is_valid_map_key(field):
    """解析出的 (level, field) 必須是 _TARGET_MAP 合法 key，否則 read_prompt 崩潰。"""
    key = (resolve_target_level(field), field)
    assert key in _TARGET_MAP, f"{key} 不在 _TARGET_MAP"
