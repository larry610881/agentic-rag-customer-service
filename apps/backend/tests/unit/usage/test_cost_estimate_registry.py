"""_estimate_cost_from_registry regression — S-LLM-Cache.2 bug。

問題：TokenUsage.model 在 ProcessDocumentUseCase 等 call site 會帶 provider 前綴
（例 "litellm:azure_ai/claude-haiku-4-5"），但 `_estimate_cost_from_registry` 建
pricing dict 時 key 是裸 model_id（"azure_ai/claude-haiku-4-5"）→ lookup miss →
cost = 0.0 永遠算不出來。

LLMCallResult.model 本身是裸 id（沒前綴）— 但多個 service 層會改寫成 last_model
帶前綴後才傳給 record_usage。兩種格式都該支援才對。
"""
from __future__ import annotations

from src.application.usage.record_usage_use_case import RecordUsageUseCase


# ── litellm provider 前綴 — 這是現實中最常見的 case ───────────────────────


def test_prefixed_litellm_model_resolves_to_correct_pricing():
    """usage.model = "litellm:azure_ai/claude-haiku-4-5" 應查到 haiku pricing。"""
    cost = RecordUsageUseCase._estimate_cost_from_registry(
        model="litellm:azure_ai/claude-haiku-4-5",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    # Haiku 4.5 input_price = $1 / MTok → 1M tokens 剛好 = $1.00
    assert cost > 0.9, f"expected ~$1.0, got {cost}"
    assert cost < 1.1


def test_bare_anthropic_model_id_still_works():
    """裸 model_id 維持原本可 lookup（直接 key match）。"""
    cost = RecordUsageUseCase._estimate_cost_from_registry(
        model="claude-haiku-4-5",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert cost > 0.9
    assert cost < 1.1


def test_prefixed_anthropic_model_also_works():
    """usage.model = "anthropic:claude-haiku-4-5" 應查到 pricing。"""
    cost = RecordUsageUseCase._estimate_cost_from_registry(
        model="anthropic:claude-haiku-4-5",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert cost > 0.9
    assert cost < 1.1


# ── 帶 cache token 的計算 — 折扣要反映在 cost ──────────────────────────────


def test_cache_read_discount_applied_for_litellm_anthropic():
    """1M cache_read_tokens 對 Haiku = $0.10（input 的 10%），遠低於純 input $1.00。"""
    cost_full = RecordUsageUseCase._estimate_cost_from_registry(
        model="litellm:azure_ai/claude-haiku-4-5",
        input_tokens=1_000_000,
        output_tokens=0,
        cache_read_tokens=0,
        cache_creation_tokens=0,
    )
    cost_cached = RecordUsageUseCase._estimate_cost_from_registry(
        model="litellm:azure_ai/claude-haiku-4-5",
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=1_000_000,  # 全 cache hit
        cache_creation_tokens=0,
    )
    assert cost_cached < cost_full * 0.2, (
        f"cache_read 應 ≤ 20% 全價，got full={cost_full}, cached={cost_cached}"
    )


def test_cache_creation_surcharge_applied_for_anthropic():
    """Claude creation 價 = input × 1.25（Anthropic 首次寫 cache 的額外成本）。"""
    cost_full = RecordUsageUseCase._estimate_cost_from_registry(
        model="anthropic:claude-haiku-4-5",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    cost_creation = RecordUsageUseCase._estimate_cost_from_registry(
        model="anthropic:claude-haiku-4-5",
        input_tokens=0,
        output_tokens=0,
        cache_creation_tokens=1_000_000,
    )
    # cache_creation_price = 1.25 × input_price = $1.25/MTok
    assert cost_creation > cost_full * 1.2, (
        f"cache_creation 應 ~1.25× 全價，got full={cost_full}, creation={cost_creation}"
    )


def test_cache_creation_also_applies_to_litellm_anthropic():
    """litellm:azure_ai/claude-* 的 cache creation 也該有 surcharge（Azure AI Claude
    跟直連 Anthropic 同定價）。S-LLM-Cache.2 發現 litellm 條目 cache_creation_price 是 0
    → 需修正為 1.25 (haiku) / 3.75 (sonnet) / 6.25 (opus)。"""
    cost_creation = RecordUsageUseCase._estimate_cost_from_registry(
        model="litellm:azure_ai/claude-haiku-4-5",
        input_tokens=0,
        output_tokens=0,
        cache_creation_tokens=1_000_000,
    )
    # 修正後預期 = $1.25 (1M × 1.25/MTok)
    assert cost_creation > 1.2, (
        f"litellm claude haiku cache_creation 應 ~$1.25/MTok，got {cost_creation}"
    )


# ── Edge cases ───────────────────────────────────────────────────────────


def test_unknown_model_returns_zero_cost():
    """不在 registry 的 model → cost = 0（fail-safe，不拋 exception）。"""
    cost = RecordUsageUseCase._estimate_cost_from_registry(
        model="unknown-provider:unknown-model",
        input_tokens=1000,
        output_tokens=500,
    )
    assert cost == 0.0


def test_empty_model_returns_zero_cost():
    cost = RecordUsageUseCase._estimate_cost_from_registry(
        model="",
        input_tokens=1000,
        output_tokens=500,
    )
    assert cost == 0.0
