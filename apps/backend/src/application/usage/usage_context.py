"""Usage 分類標記解析策略（Issue #54 Phase B，spec §7.2/§7.3）

純邏輯、無框架依賴；interfaces 層的 FastAPI dependency 只是薄轉接。
eval/optimizer/playground 流量以 header 標記分流：授權以 JWT role 判定
（`identity_source` 是 body 自報值、可偽造，不可作依據）；任何不合法情況
一律 fallback `chat_web`（fail-open：標記失敗不得影響對話主流程）。

channel-parity 合規：解析邏輯單一實作於此；widget/LINE 通路架構上不存在
eval 流量（AgentAPIClient 只打 /agent/chat），不適用此標記。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.domain.usage.category import UsageCategory

logger = logging.getLogger(__name__)

USAGE_CATEGORY_HEADER = "x-usage-category"
EVAL_RUN_ID_HEADER = "x-eval-run-id"

# 只有這三個分類可經 header 標記；其餘 UsageCategory 值不接受（防濫標）
_EVAL_CATEGORIES = frozenset(
    {
        UsageCategory.EVAL_GATE.value,
        UsageCategory.PROMPT_OPTIMIZE.value,
        UsageCategory.PLAYGROUND.value,
    }
)

# 可標記 eval 流量的角色（真實授權訊號 = JWT role）
_ALLOWED_ROLES = frozenset({"system_admin", "tenant_admin"})


@dataclass(frozen=True)
class UsageContext:
    request_type: str = UsageCategory.CHAT_WEB.value
    run_id: str | None = None


def resolve_usage_context(
    category: str | None,
    run_id: str | None,
    role: str | None,
) -> UsageContext:
    """header 值 + JWT role → 記帳分類。不合法一律 fallback chat_web。"""
    if not category:
        return UsageContext()
    if category not in _EVAL_CATEGORIES or role not in _ALLOWED_ROLES:
        logger.warning(
            "usage_context.rejected category=%r role=%r (fallback chat_web)",
            category,
            role,
        )
        return UsageContext()
    return UsageContext(request_type=category, run_id=run_id or None)
