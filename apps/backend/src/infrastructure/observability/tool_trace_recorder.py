"""Tool trace metadata recorder.

把 tool 執行完的原始 payload 寫入 ExecutionNode.metadata，讓 trace viewer
能還原 tool 實際傳出了什麼（contact / sources / card ...）。

設計動機（BUG-01）：原本 react_agent_service 只存 result_preview 字串，
導致觀測性介面看不到結構化 payload，且歷史對話也無法還原 rich content。
"""

from __future__ import annotations

import json
from typing import Any

from src.domain.observability.agent_trace import ExecutionNode


def record_tool_output(node: ExecutionNode, content_str: str) -> None:
    """解析 tool 輸出並將結構化 payload 塞進 node.metadata。

    JSON dict → metadata["tool_output"] = dict；若含 contact 另存 metadata["contact"]。
    純文字或 list → 不寫入，由 result_preview 擔任 fallback。
    """
    parsed: Any
    try:
        parsed = json.loads(content_str)
    except (json.JSONDecodeError, TypeError):
        return

    if not isinstance(parsed, dict):
        return

    node.metadata["tool_output"] = parsed

    contact = parsed.get("contact")
    if isinstance(contact, dict):
        node.metadata["contact"] = contact
