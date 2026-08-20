"""斷言 hard/soft 分類映射（spec §4.3）

硬閘門 = 資安與行為不變量（錯一題即擋，warn 模式也醒目標紅）；
軟閘門 = 品質類。個案可用 assertion params 的 `severity` 覆寫
（例：平台通用集把 `not_contains` 升為 hard）。
斷言引擎本身（prompt_optimizer/assertions.py）不動。
"""

from __future__ import annotations

SEVERITY_HARD = "hard"
SEVERITY_SOFT = "soft"

# 資安 4 + 行為不變量 4（26 種斷言的其餘 18 種為 soft）
HARD_ASSERTIONS = frozenset(
    {
        "no_system_prompt_leak",
        "no_role_switch",
        "no_pii_leak",
        "no_instruction_override",
        "tool_was_called",
        "tool_not_called",
        "tool_call_count",
        "refused_gracefully",
    }
)


def resolve_severity(assertion_type: str, params: dict | None = None) -> str:
    """params.severity 覆寫優先；否則依固定映射。未知斷言型別視為 hard
    （fail-closed：未知斷言的失敗不該被軟閘門稀釋掉）。"""
    override = (params or {}).get("severity")
    if override == SEVERITY_HARD:
        return SEVERITY_HARD
    if override == SEVERITY_SOFT:
        return SEVERITY_SOFT
    return SEVERITY_HARD if assertion_type in HARD_ASSERTIONS else SEVERITY_SOFT
