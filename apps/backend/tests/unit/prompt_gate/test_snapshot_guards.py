"""快照白名單守衛（Phase A 學習筆記債 + Phase C gate 欄位紅線）

1. Bot 實體欄位 − 白名單 − 顯式排除清單 = ∅：
   新增實體欄位時必須「顯式」決定入不入快照，漏判即紅燈。
2. gate 治理欄位絕不入快照（否則改閘門設定會自我觸發版本）。
3. Verdict 門檻與 prompt_optimizer 現值一致（fence）。
"""

import dataclasses

from prompt_optimizer.evaluator import VALIDATION_THRESHOLDS
from src.domain.bot.entity import Bot
from src.domain.prompt_gate.config_snapshot import (
    SNAPSHOT_FIELDS,
    take_snapshot,
)
from src.domain.prompt_gate.verdict import PRIORITY_THRESHOLDS

# 顯式排除清單：不入快照的欄位與「為什麼」的分類
_EXCLUDED_FIELDS = {
    # 識別/中繼
    "id", "short_code", "tenant_id", "name", "description",
    "created_at", "updated_at",
    # 憑證（紅線：入快照 = 秘密擴散 + 回朔誤還原舊金鑰）
    "line_channel_secret", "line_channel_access_token",
    # 外觀/營運（直接更新、不產生版本）
    "is_active", "fab_icon_url", "widget_enabled",
    "widget_allowed_origins", "widget_keep_history",
    "widget_welcome_message", "widget_placeholder_text",
    "widget_greeting_messages", "widget_greeting_animation",
    "show_sources", "line_show_sources", "busy_reply_message",
    "customer_service_url",
    # 治理/觀測（入快照會出現「回朔把閘門關掉」自指問題）
    "eval_provider", "eval_model", "eval_depth",
    "gate_mode", "gate_soft_threshold", "gate_repeats",
    "gate_auto_publish", "gate_daily_limit", "gate_budget_usd",
    # Deprecated / legacy
    "intent_routes", "mcp_servers",
}


def test_entity_fields_fully_classified():
    """實體欄位 − 白名單 − 排除清單 = ∅（漏分類即紅燈）。"""
    entity_fields = {f.name for f in dataclasses.fields(Bot)}
    unclassified = entity_fields - set(SNAPSHOT_FIELDS) - _EXCLUDED_FIELDS
    assert unclassified == set(), (
        f"Bot 新欄位未分類（入快照加 SNAPSHOT_FIELDS，"
        f"不入加 _EXCLUDED_FIELDS 並註明理由）: {sorted(unclassified)}"
    )
    # 反向：白名單/排除清單不得含不存在的欄位（防 typo 與欄位改名漂移）
    ghost = (set(SNAPSHOT_FIELDS) | _EXCLUDED_FIELDS) - entity_fields
    assert ghost == set(), f"清單含不存在的欄位: {sorted(ghost)}"
    # 且互斥
    assert set(SNAPSHOT_FIELDS) & _EXCLUDED_FIELDS == set()


def test_gate_fields_never_in_snapshot():
    bot = Bot(tenant_id="t", name="b", gate_mode="block")
    snap = take_snapshot(bot)
    for f in (
        "gate_mode", "gate_soft_threshold", "gate_repeats",
        "gate_auto_publish", "gate_daily_limit", "gate_budget_usd",
    ):
        assert f not in snap, f"gate 治理欄位 {f} 不得入快照"


def test_verdict_thresholds_match_evaluator():
    """PRIORITY_THRESHOLDS 沿用 evaluator.VALIDATION_THRESHOLDS 現值；
    任一邊改動必須同步（兩處語意都是「case 級軟通過門檻」）。"""
    assert PRIORITY_THRESHOLDS == VALIDATION_THRESHOLDS
