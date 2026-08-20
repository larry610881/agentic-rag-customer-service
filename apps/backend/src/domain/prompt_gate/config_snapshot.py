"""Bot 設定快照：白名單序列化、diff、overlay 套用

快照 = bot 行為設定的不可變 JSON 快照（config as commit）。
白名單三分法（spec §13.1）：
- 進快照：prompt 類 / LLM 參數 / RAG 檢索 / Agent 行為
- 不進：識別中繼、憑證（紅線）、外觀營運、治理觀測欄位
mcp_bindings 剝除 env_values（只存 registry_id + enabled_tools），
overlay 還原時以 registry_id 對回現行加密值。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from src.domain.bot.entity import Bot, BotMcpBinding, ToolRagConfig

SNAPSHOT_SCHEMA = 1

# prompt 類欄位（第 0 層靜態檢查的施作對象）
PROMPT_FIELDS = (
    "base_prompt",
    "bot_prompt",
    "memory_extraction_prompt",
    "query_rewrite_extra_hint",
    "hyde_extra_hint",
)

# 直接以原值進出快照的純量/list 欄位
_SCALAR_FIELDS = (
    *PROMPT_FIELDS,
    "llm_provider",
    "llm_model",
    "router_model",
    "summary_model",
    "rag_retrieval_modes",
    "query_rewrite_enabled",
    "query_rewrite_model",
    "hyde_enabled",
    "hyde_model",
    "rerank_enabled",
    "rerank_model",
    "rerank_top_n",
    "enabled_tools",
    "max_tool_calls",
    "memory_enabled",
    "memory_extraction_threshold",
    "knowledge_base_ids",
)

# llm_params 巢狀 VO 的子欄位
_LLM_PARAM_FIELDS = (
    "temperature",
    "max_tokens",
    "history_limit",
    "frequency_penalty",
    "reasoning_effort",
    "rag_top_k",
    "rag_score_threshold",
)

# 快照的全部頂層 key（含巢狀欄位）
SNAPSHOT_FIELDS = (*_SCALAR_FIELDS, "llm_params", "tool_configs", "mcp_bindings")


@dataclass(frozen=True)
class SnapshotApplyResult:
    """overlay 套用結果：applied 為實際套用的欄位，skipped 為快照缺少
    （該版之後才新增的欄位）而保留現值的欄位。"""

    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _tool_configs_to_dict(tool_configs: dict[str, ToolRagConfig]) -> dict:
    out: dict[str, dict] = {}
    for name, cfg in (tool_configs or {}).items():
        entry = {
            "rag_top_k": cfg.rag_top_k,
            "rag_score_threshold": cfg.rag_score_threshold,
            "rerank_enabled": cfg.rerank_enabled,
            "rerank_model": cfg.rerank_model,
            "rerank_top_n": cfg.rerank_top_n,
            "kb_ids": list(cfg.kb_ids) if cfg.kb_ids is not None else None,
        }
        out[name] = {k: v for k, v in entry.items() if v is not None}
    return out


def _dict_to_tool_configs(raw: dict) -> dict[str, ToolRagConfig]:
    result: dict[str, ToolRagConfig] = {}
    for name, params in (raw or {}).items():
        if not isinstance(params, dict):
            continue
        kb_ids = params.get("kb_ids")
        result[name] = ToolRagConfig(
            rag_top_k=params.get("rag_top_k"),
            rag_score_threshold=params.get("rag_score_threshold"),
            rerank_enabled=params.get("rerank_enabled"),
            rerank_model=params.get("rerank_model"),
            rerank_top_n=params.get("rerank_top_n"),
            kb_ids=list(kb_ids) if isinstance(kb_ids, list) else None,
        )
    return result


def take_snapshot(bot: Bot) -> dict:
    """對 Bot 取白名單設定快照。憑證與外觀營運欄位絕不進入。"""
    snapshot: dict = {}
    for f in _SCALAR_FIELDS:
        value = getattr(bot, f)
        snapshot[f] = list(value) if isinstance(value, list) else value
    snapshot["llm_params"] = {
        k: getattr(bot.llm_params, k) for k in _LLM_PARAM_FIELDS
    }
    snapshot["tool_configs"] = _tool_configs_to_dict(bot.tool_configs)
    # 紅線：env_values（可能含加密金鑰）剝除
    snapshot["mcp_bindings"] = [
        {"registry_id": b.registry_id, "enabled_tools": list(b.enabled_tools)}
        for b in (bot.mcp_bindings or [])
    ]
    return snapshot


def diff_snapshots(old: dict, new: dict) -> list[str]:
    """比較兩份快照，回傳變更欄位清單。
    llm_params 展開為 `llm_params.<子欄位>`，其餘以頂層欄位為粒度。
    只比對雙方皆存在的欄位（舊 schema 快照缺欄位不視為變更）。"""
    changed: list[str] = []
    for f in _SCALAR_FIELDS + ("tool_configs", "mcp_bindings"):
        if f in old and f in new and old[f] != new[f]:
            changed.append(f)
    old_llm = old.get("llm_params") or {}
    new_llm = new.get("llm_params") or {}
    for k in _LLM_PARAM_FIELDS:
        if k in old_llm and k in new_llm and old_llm[k] != new_llm[k]:
            changed.append(f"llm_params.{k}")
    return changed


def apply_snapshot(bot: Bot, snapshot: dict) -> SnapshotApplyResult:
    """Overlay 套用：快照有的欄位套用到 Bot，缺的保留現值（定案 12）。
    mcp_bindings 以 registry_id 對回現行 env_values（憑證不被回朔動到）。"""
    applied: list[str] = []
    skipped: list[str] = []

    for f in _SCALAR_FIELDS:
        if f not in snapshot:
            skipped.append(f)
            continue
        value = snapshot[f]
        setattr(bot, f, list(value) if isinstance(value, list) else value)
        applied.append(f)

    if "llm_params" in snapshot:
        raw = snapshot["llm_params"] or {}
        changes = {k: raw[k] for k in _LLM_PARAM_FIELDS if k in raw}
        bot.llm_params = replace(bot.llm_params, **changes)
        applied.append("llm_params")
    else:
        skipped.append("llm_params")

    if "tool_configs" in snapshot:
        bot.tool_configs = _dict_to_tool_configs(snapshot["tool_configs"])
        applied.append("tool_configs")
    else:
        skipped.append("tool_configs")

    if "mcp_bindings" in snapshot:
        current_env = {
            b.registry_id: b.env_values for b in (bot.mcp_bindings or [])
        }
        bot.mcp_bindings = [
            BotMcpBinding(
                registry_id=b.get("registry_id", ""),
                enabled_tools=list(b.get("enabled_tools", [])),
                env_values=dict(current_env.get(b.get("registry_id", ""), {})),
            )
            for b in snapshot["mcp_bindings"]
            if isinstance(b, dict)
        ]
        applied.append("mcp_bindings")
    else:
        skipped.append("mcp_bindings")

    return SnapshotApplyResult(applied=applied, skipped=skipped)
