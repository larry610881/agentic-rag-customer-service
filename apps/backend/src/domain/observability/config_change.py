"""設定變更通知 — 欄位群組（Issue #77）

管理端稽核列（bot / worker / 租戶防護）的 changed_fields 對應到五個欄位群組；
租戶只勾選「哪些群組變更要通知」，不用逐欄位設定。未列入任何群組的欄位
（名稱、描述、排序、外觀……）永不觸發通知。
"""

from __future__ import annotations

from collections.abc import Iterable

GROUP_MODEL = "model"
GROUP_PROMPT = "prompt"
GROUP_KNOWLEDGE = "knowledge"
GROUP_TOOLS = "tools"
GROUP_GUARD = "guard"

# 顯示順序即群組固定順序
GROUP_ORDER: tuple[str, ...] = (
    GROUP_MODEL, GROUP_PROMPT, GROUP_KNOWLEDGE, GROUP_TOOLS, GROUP_GUARD,
)

GROUP_LABELS: dict[str, str] = {
    GROUP_MODEL: "模型",
    GROUP_PROMPT: "提示詞",
    GROUP_KNOWLEDGE: "知識庫",
    GROUP_TOOLS: "工具",
    GROUP_GUARD: "防護",
}

# 群組 → 欄位（bot 稽核視圖 + worker 稽核視圖 + guard_settings overrides 鍵）
CONFIG_CHANGE_FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    GROUP_MODEL: (
        "llm_provider", "llm_model", "llm_params",
        "router_model", "summary_model", "query_rewrite_model", "hyde_model",
        "rerank_model",
        # worker 的 llm 參數是頂層欄位
        "temperature", "max_tokens", "reasoning_effort", "history_limit",
        "frequency_penalty",
    ),
    GROUP_PROMPT: (
        "bot_prompt", "base_prompt", "worker_prompt", "memory_extraction_prompt",
        "query_rewrite_extra_hint", "hyde_extra_hint", "miss_reply",
    ),
    GROUP_KNOWLEDGE: (
        "knowledge_base_ids", "rag_retrieval_modes", "rag_top_k",
        "rag_score_threshold", "rerank_enabled", "rerank_top_n",
        "query_rewrite_enabled", "hyde_enabled", "tool_configs",
        "memory_enabled", "memory_extraction_threshold",
    ),
    GROUP_TOOLS: (
        "enabled_tools", "mcp_bindings", "enabled_mcp_ids", "max_tool_calls",
        "intent_routes", "direct_retrieval",
    ),
    GROUP_GUARD: (
        "guard_stages", "mode", "output_format", "output_schema",
        "output_text_field", "llm_input_guard_enabled",
        # guard_settings（租戶 scope）overrides 鍵
        "stages", "required_stages", "profile", "locked",
    ),
}

_FIELD_TO_GROUP: dict[str, str] = {
    f: g for g, fields in CONFIG_CHANGE_FIELD_GROUPS.items() for f in fields
}

# 平台預設：租戶未設定時只通知模型與提示詞變更
DEFAULT_NOTIFY_GROUPS: tuple[str, ...] = (GROUP_MODEL, GROUP_PROMPT)

# 會觸發設定變更通知的稽核實體（都是租戶 scope；guard_settings 只有 tenant scope
# 的列帶 tenant_id）
NOTIFIABLE_ENTITY_TYPES: frozenset[str] = frozenset({"bot", "worker", "guard_settings"})
GUARD_SETTINGS_ENTITY = "guard_settings"

# 通知內容只顯示字數、不顯示全文的欄位
LONG_TEXT_FIELDS: frozenset[str] = frozenset({
    "bot_prompt", "base_prompt", "worker_prompt", "memory_extraction_prompt",
    "query_rewrite_extra_hint", "hyde_extra_hint", "miss_reply",
})

# 通知內容的欄位標籤（未列者以原欄位名顯示）
FIELD_LABELS: dict[str, str] = {
    "llm_provider": "模型供應商",
    "llm_model": "模型",
    "llm_params": "模型參數",
    "router_model": "分流模型",
    "summary_model": "摘要模型",
    "query_rewrite_model": "改寫模型",
    "hyde_model": "HyDE 模型",
    "rerank_model": "重排模型",
    "temperature": "溫度",
    "max_tokens": "最大輸出 token",
    "reasoning_effort": "推理強度",
    "bot_prompt": "機器人提示詞",
    "base_prompt": "基礎提示詞",
    "worker_prompt": "worker 提示詞",
    "memory_extraction_prompt": "記憶萃取提示詞",
    "miss_reply": "未命中話術",
    "knowledge_base_ids": "知識庫",
    "rag_retrieval_modes": "檢索模式",
    "rag_top_k": "檢索筆數",
    "rag_score_threshold": "檢索門檻",
    "rerank_enabled": "重排",
    "rerank_top_n": "重排筆數",
    "tool_configs": "工具檢索設定",
    "enabled_tools": "啟用工具",
    "mcp_bindings": "MCP 綁定",
    "enabled_mcp_ids": "MCP 綁定",
    "max_tool_calls": "工具呼叫上限",
    "intent_routes": "意圖路由",
    "direct_retrieval": "快速道",
    "guard_stages": "防護階段",
    "mode": "模式",
    "output_format": "輸出格式",
    "output_schema": "輸出 schema",
    "stages": "防護階段",
    "required_stages": "必開階段",
    "profile": "防護方案",
    "locked": "鎖定",
}


def field_group(field: str, entity_type: str | None = None) -> str | None:
    """欄位所屬群組；guard_settings 的所有鍵一律視為防護群組。"""
    if entity_type == GUARD_SETTINGS_ENTITY:
        return GROUP_GUARD
    return _FIELD_TO_GROUP.get(field)


def groups_touched(
    changed_fields: Iterable[str], entity_type: str | None = None
) -> list[str]:
    """變更欄位觸及的群組（依 GROUP_ORDER 排序、去重）。"""
    touched = {
        g for g in (field_group(f, entity_type) for f in changed_fields) if g
    }
    return [g for g in GROUP_ORDER if g in touched]


def validate_notify_groups(groups: list[str] | None) -> list[str] | None:
    """租戶偏好寫入前驗證：None 原樣回傳；未知群組 raise ValueError；去重保序。"""
    if groups is None:
        return None
    unknown = [g for g in groups if g not in GROUP_LABELS]
    if unknown:
        raise ValueError(
            f"unknown notify groups: {', '.join(unknown)}; "
            f"allowed: {', '.join(GROUP_ORDER)}"
        )
    seen: list[str] = []
    for g in groups:
        if g not in seen:
            seen.append(g)
    return seen


def effective_notify_groups(configured: list[str] | None) -> list[str]:
    """租戶生效的群組：None → 平台預設；[] → 完全關閉。"""
    if configured is None:
        return list(DEFAULT_NOTIFY_GROUPS)
    return [g for g in GROUP_ORDER if g in configured]


def groups_to_notify(
    *,
    entity_type: str,
    changed_fields: Iterable[str],
    configured: list[str] | None,
) -> list[str]:
    """此筆稽核該通知的群組 = 觸及群組 ∩ 租戶生效群組（空 = 不通知）。"""
    if entity_type not in NOTIFIABLE_ENTITY_TYPES:
        return []
    enabled = set(effective_notify_groups(configured))
    return [g for g in groups_touched(changed_fields, entity_type) if g in enabled]


def field_label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def group_label(group: str) -> str:
    return GROUP_LABELS.get(group, group)
