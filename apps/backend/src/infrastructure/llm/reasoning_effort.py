"""Issue #72：推理強度（reasoning_effort）「要求值 vs 實際送出值」解析

bot 設定的 reasoning_effort（none | low | medium | high）不一定能原樣送到供應商：
- OpenAI gpt-5.x 綁 function tools 只收 none；gpt-4o 系完全不收
- Gemini（OpenAI 相容端點）直傳，minimal → low
- Anthropic：none → 不帶 thinking（Opus 5 / Sonnet 5 明確 disabled）；
  low/medium/high → adaptive thinking + output_config.effort；舊模型丟棄

各 provider service 各自做 gate；本模組把「同一套判斷」以純函式暴露給 trace，
讓 agent_llm 節點能記 `reasoning_effort_requested` / `reasoning_effort_effective`。

Issue #76：同模組另放 Anthropic 取樣參數（temperature / top_p / top_k）
是否可送的模型表 `sampling_params_allowed`，供 anthropic_llm_service 與
react_agent_service 共用。
"""

from __future__ import annotations

from typing import Any

PROVIDER_DEFAULT = "provider_default"
_ANTHROPIC_PROVIDERS = ("anthropic", "claude")

# === Issue #76：Anthropic 取樣參數（temperature / top_p / top_k）模型表 ======
#
# 依 claude-api skill：
# - shared/error-codes.md「Model-specific 400s on Claude Opus 5 / Fable 5/5.1 /
#   Opus 4.8 / 4.7」：`temperature`, `top_p`, `top_k` are removed - sending any
#   of them returns 400.
# - shared/model-migration.md §Migrating to Opus 4.7「Sampling parameters
#   removed」：Requests that include them return a 400 error；Opus 4.8 / Opus 5 /
#   Fable 5 沿用同一 request surface（still rejected）。
# - shared/model-migration.md §Migrating to Sonnet 5「Sampling parameters
#   rejected」：非預設值回 400，省略或送預設值仍接受 → 本專案一律不送。
# - Opus 4.6 / Sonnet 4.6 / 4.5 / 4.x / 3.x：Allowed（Thinking & Effort 表）；
#   未知模型視為允許（維持既有行為，由 API 決定）。
_ANTHROPIC_NO_SAMPLING_PREFIXES = (
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-mythos-5",
    "claude-mythos-preview",
)


def _normalize_anthropic_model(model: str) -> str:
    """去掉 Bedrock / Vertex 的供應商前綴（如 ``anthropic.`` / ``us.anthropic.``），
    只留 ``claude-...`` 本體，並轉小寫。"""
    lowered = (model or "").strip().lower()
    idx = lowered.find("claude-")
    return lowered[idx:] if idx > 0 else lowered


def sampling_params_allowed(model: str) -> bool:
    """Anthropic 模型是否接受 temperature / top_p / top_k。

    False：Opus 4.7 / 4.8 / Opus 5 / Fable 5 / 5.1 / Mythos（送任一即 400）、
    Sonnet 5（只收預設值，本專案一律不送）。
    True：Opus 4.6 / Sonnet 4.6 / 4.5 / 4.x / 3.x 與未知模型。
    """
    normalized = _normalize_anthropic_model(model)
    return not any(normalized.startswith(p) for p in _ANTHROPIC_NO_SAMPLING_PREFIXES)


def effective_reasoning_effort(
    provider: str, model: str, requested: str | None
) -> str | None:
    """回傳實際送出的推理強度；None = 未要求；PROVIDER_DEFAULT = 要求值被丟棄。"""
    if not requested:
        return None
    # 延遲 import：anthropic_llm_service 於模組層 import 本模組的
    # sampling_params_allowed（Issue #76），頂層互相 import 會循環。
    from src.infrastructure.llm.anthropic_llm_service import anthropic_thinking_config
    from src.infrastructure.llm.openai_llm_service import (
        normalize_reasoning_effort,
        reasoning_effort_allowed,
    )

    if provider in _ANTHROPIC_PROVIDERS:
        _thinking, _effort, effective = anthropic_thinking_config(model, requested)
        return effective if effective is not None else PROVIDER_DEFAULT
    # OpenAI / Gemini / 其他 OpenAI 相容端點
    # （與 get_chat_model / _create_chat_model 同一套 gate）
    if reasoning_effort_allowed(model, requested):
        return normalize_reasoning_effort(model, requested)
    return PROVIDER_DEFAULT


def describe_reasoning_effort(llm_params: dict[str, Any] | None) -> dict[str, Any]:
    """從 llm_params 產生 trace 節點用的 metadata（未要求時回空 dict）。"""
    params = llm_params or {}
    requested = params.get("reasoning_effort")
    if not requested:
        return {}
    return {
        "reasoning_effort_requested": requested,
        "reasoning_effort_effective": effective_reasoning_effort(
            str(params.get("provider_name", "") or ""),
            str(params.get("model", "") or ""),
            str(requested),
        ),
    }
