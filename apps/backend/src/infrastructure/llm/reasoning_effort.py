"""Issue #72：推理強度（reasoning_effort）「要求值 vs 實際送出值」解析

bot 設定的 reasoning_effort（none | low | medium | high）不一定能原樣送到供應商：
- OpenAI gpt-5.x 綁 function tools 只收 none；gpt-4o 系完全不收
- Gemini（OpenAI 相容端點）直傳，minimal → low
- Anthropic：none → 不帶 thinking（Opus 5 / Sonnet 5 明確 disabled）；
  low/medium/high → adaptive thinking + output_config.effort；舊模型丟棄

各 provider service 各自做 gate；本模組把「同一套判斷」以純函式暴露給 trace，
讓 agent_llm 節點能記 `reasoning_effort_requested` / `reasoning_effort_effective`。
"""

from __future__ import annotations

from typing import Any

from src.infrastructure.llm.anthropic_llm_service import anthropic_thinking_config
from src.infrastructure.llm.openai_llm_service import (
    normalize_reasoning_effort,
    reasoning_effort_allowed,
)

PROVIDER_DEFAULT = "provider_default"
_ANTHROPIC_PROVIDERS = ("anthropic", "claude")


def effective_reasoning_effort(
    provider: str, model: str, requested: str | None
) -> str | None:
    """回傳實際送出的推理強度；None = 未要求；PROVIDER_DEFAULT = 要求值被丟棄。"""
    if not requested:
        return None
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
