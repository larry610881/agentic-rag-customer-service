"""BDD step defs — unit/usage/record_usage_with_db_pricing.feature"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.pricing.entity import ModelPricing
from src.domain.pricing.value_objects import PriceRate
from src.domain.rag.value_objects import TokenUsage
from src.infrastructure.pricing.pricing_cache import InMemoryPricingCache

scenarios("unit/usage/record_usage_with_db_pricing.feature")


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def context():
    return {}


class _FakeRepo:
    def __init__(self, items):
        self._items = items

    async def list_all_for_cache(self):
        return list(self._items)


@given(
    parsers.parse(
        'PricingCache 已載入 "{provider}" "{model_id}" input={inp:g} output={out:g}'
    )
)
def seed_cache(context, provider, model_id, inp, out):
    items = [
        ModelPricing(
            provider=provider,
            model_id=model_id,
            display_name=model_id,
            rate=PriceRate(inp, out),
            effective_from=_now() - timedelta(hours=1),
            created_by="seed",
            note="seed",
        )
    ]
    cache = InMemoryPricingCache(repo_factory=lambda: _FakeRepo(items))
    run(cache.refresh())
    context["cache"] = cache
    context["seed_cache"] = True


@given(parsers.parse('PricingCache 對 "{spec}" 回傳 None'))
def seed_cache_miss(context, spec):
    cache = InMemoryPricingCache(repo_factory=lambda: _FakeRepo([]))
    run(cache.refresh())
    context["cache"] = cache
    context["seed_cache"] = False


@given(
    parsers.parse(
        'DEFAULT_MODELS 有 "{provider}" "{model_id}" input={inp:g} output={out:g}'
    )
)
def note_default_models(context, provider, model_id, inp, out):
    # DEFAULT_MODELS 已經 hardcode 了 "anthropic/claude-haiku-4-5" input=1.0 output=5.0
    # 這裡只存期待值給 Then 斷言用
    context["default_models_price"] = {
        "input": inp,
        "output": out,
    }


@given(parsers.parse('PricingCache 已載入 "{provider}" "{model_id}"'))
def seed_cache_simple(context, provider, model_id):
    seed_cache(context, provider, model_id, 1.20, 6.00)


# Hack: track if lookup called
class _SpyCache(InMemoryPricingCache):
    def __init__(self, inner):
        self.inner = inner
        self.calls = 0

    def lookup(self, model_spec, at):
        self.calls += 1
        return self.inner.lookup(model_spec=model_spec, at=at)

    async def refresh(self):
        await self.inner.refresh()


@when(
    parsers.parse(
        'RecordUsageUseCase 收到一筆 TokenUsage model="{model}" estimated_cost={cost:g} input_tokens={it:d} output_tokens={ot:d}'
    )
)
def record(context, model, cost, it, ot):
    usage_repo = AsyncMock()
    usage_repo.save = AsyncMock()

    cache = context.get("cache")
    spy = _SpyCache(cache) if cache else None
    context["spy"] = spy

    uc = RecordUsageUseCase(
        usage_repository=usage_repo,
        pricing_cache=spy,
    )
    usage = TokenUsage(
        model=model,
        input_tokens=it,
        output_tokens=ot,
        estimated_cost=cost,
    )
    run(
        uc.execute(
            tenant_id="t1",
            request_type="chat_web",
            usage=usage,
        )
    )
    # capture the saved record
    context["saved_record"] = usage_repo.save.await_args.args[0]


@when(
    parsers.parse(
        'RecordUsageUseCase 收到一筆 TokenUsage model="{model}" estimated_cost={cost:g}'
    )
)
def record_simple(context, model, cost):
    record(context, model, cost, 1000, 500)


@then(
    parsers.parse(
        "儲存的 UsageRecord.estimated_cost 應以 DB 價格計算 input={inp:g} output={out:g}"
    )
)
def assert_db_priced(context, inp, out):
    saved = context["saved_record"]
    expected = 1000 * inp / 1_000_000 + 500 * out / 1_000_000
    assert saved.estimated_cost == pytest.approx(expected, rel=1e-6)


@then("UsageRecord.estimated_cost 不應為 0")
def assert_not_zero(context):
    assert context["saved_record"].estimated_cost > 0


@then("儲存的 UsageRecord.estimated_cost 應以 DEFAULT_MODELS 價格計算")
def assert_default_priced(context):
    saved = context["saved_record"]
    d = context["default_models_price"]
    expected = 1000 * d["input"] / 1_000_000 + 500 * d["output"] / 1_000_000
    assert saved.estimated_cost == pytest.approx(expected, rel=1e-6)


@then(parsers.parse("儲存的 UsageRecord.estimated_cost 應為 {cost:g}"))
def assert_cost_equals(context, cost):
    assert context["saved_record"].estimated_cost == pytest.approx(cost)


@then("PricingCache.lookup 不應被呼叫")
def assert_no_cache_call(context):
    spy = context["spy"]
    # usage.estimated_cost > 0 → 不走 fallback → 不呼叫 cache
    assert spy is None or spy.calls == 0
