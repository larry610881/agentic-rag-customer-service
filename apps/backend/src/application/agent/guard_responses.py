"""防護攔截回應的共用組裝（channel-parity 債務第 3 項）。

regex 輸入防護與分類器攻擊短路命中後，三通路都要回同一份固定文案、守住 bot 的輸出格式、
帶 guard_blocked / guard_rule_matched；以前 web 與 LINE 各組一次，LINE 漏了
structured_output。
"""

from __future__ import annotations

from typing import Any

from src.application.agent.output_format import OutputSpec, resolve_guard_blocked
from src.domain.agent.entity import AgentResponse


def blocked_input_response(
    guard_result: Any, output_spec: OutputSpec | None
) -> AgentResponse:
    """從 blocked GuardResult 組攔截回應；json bot 同時帶已解析物件。"""
    blocked = (
        resolve_guard_blocked(output_spec, guard_result.blocked_response)
        if output_spec is not None
        else None
    )
    return AgentResponse(
        answer=blocked.text if blocked else guard_result.blocked_response,
        structured_output=blocked.parsed if blocked else None,
        guard_blocked="input",
        guard_rule_matched=getattr(guard_result, "rule_matched", None),
    )
