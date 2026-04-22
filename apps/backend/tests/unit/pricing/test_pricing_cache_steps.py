"""BDD step defs — unit/pricing/pricing_cache.feature"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.pricing.entity import ModelPricing
from src.domain.pricing.value_objects import PriceRate
from src.infrastructure.pricing.pricing_cache import InMemoryPricingCache
from tests.unit.pricing.conftest import FakeModelPricingRepo, run

scenarios("unit/pricing/pricing_cache.feature")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@given("DB 有 3 筆生效中的 pricing: openai/gpt-5, anthropic/claude-haiku-4-5, litellm/azure_ai/claude-sonnet-4-5")
def seed_three(context):
    repo = FakeModelPricingRepo()
    past = _now() - timedelta(hours=1)
    for provider, mid in [
        ("openai", "gpt-5"),
        ("anthropic", "claude-haiku-4-5"),
        ("litellm", "azure_ai/claude-sonnet-4-5"),
    ]:
        run(
            repo.save(
                ModelPricing(
                    provider=provider,
                    model_id=mid,
                    display_name=mid,
                    rate=PriceRate(1.0, 5.0),
                    effective_from=past,
                    created_by="seed",
                    note="seed",
                )
            )
        )
    context["repo"] = repo


@when("PricingCache 啟動載入")
def cache_startup(context):
    cache = InMemoryPricingCache(repo_factory=lambda: context["repo"])
    run(cache.refresh())
    context["cache"] = cache


@then("cache 應包含 3 組 (provider, model_id) 的索引")
def assert_three_entries(context):
    cache = context["cache"]
    assert len(cache._index) == 3


@given(
    parsers.parse(
        'PricingCache 已載入 "{provider}" "{model_id}" input={inp:g} output={out:g}'
    )
)
def seed_one_into_cache(context, provider, model_id, inp, out):
    context.setdefault("repo", FakeModelPricingRepo())
    run(
        context["repo"].save(
            ModelPricing(
                provider=provider,
                model_id=model_id,
                display_name=model_id,
                rate=PriceRate(inp, out),
                effective_from=_now() - timedelta(hours=1),
                created_by="seed",
                note="seed",
            )
        )
    )
    cache = InMemoryPricingCache(repo_factory=lambda: context["repo"])
    run(cache.refresh())
    context["cache"] = cache


@given(
    parsers.parse('PricingCache 已載入 "{provider}" "{model_id}" input={inp:g}')
)
def seed_one_only_input(context, provider, model_id, inp):
    seed_one_into_cache(context, provider, model_id, inp, 5.0)


@given("PricingCache 為空")
def empty_cache(context):
    repo = FakeModelPricingRepo()
    context["repo"] = repo
    cache = InMemoryPricingCache(repo_factory=lambda: repo)
    run(cache.refresh())
    context["cache"] = cache


@when(parsers.parse('查詢 "{model_spec}" at=now'))
def lookup_now(context, model_spec):
    context["lookup_result"] = context["cache"].lookup(
        model_spec=model_spec, at=_now()
    )


@then(parsers.parse('應回傳 dict 含 input={inp:g} output={out:g}'))
def assert_dict_values(context, inp, out):
    result = context["lookup_result"]
    assert result is not None
    assert result["input"] == pytest.approx(inp)
    assert result["output"] == pytest.approx(out)


@then("應回傳 None")
def assert_none(context):
    assert context["lookup_result"] is None


@given(
    "PricingCache 有 \"openai\" \"gpt-5\" 兩個版本: v1 effective_from=T0, v2 effective_from=T1"
)
def seed_two_versions(context):
    repo = FakeModelPricingRepo()
    t0 = _now() - timedelta(hours=3)
    t1 = _now() - timedelta(hours=1)
    # v1 的 effective_to = v2.effective_from（append-only 規則）
    run(
        repo.save(
            ModelPricing(
                provider="openai",
                model_id="gpt-5",
                display_name="gpt-5",
                rate=PriceRate(1.0, 5.0),
                effective_from=t0,
                effective_to=t1,
                created_by="seed",
                note="v1",
            )
        )
    )
    run(
        repo.save(
            ModelPricing(
                provider="openai",
                model_id="gpt-5",
                display_name="gpt-5",
                rate=PriceRate(2.0, 10.0),
                effective_from=t1,
                created_by="seed",
                note="v2",
            )
        )
    )
    cache = InMemoryPricingCache(repo_factory=lambda: repo)
    run(cache.refresh())
    context["cache"] = cache
    context["t0"] = t0
    context["t1"] = t1


@when(parsers.parse('查詢 "{model_spec}" at=T0+1sec'))
def lookup_t0(context, model_spec):
    at = context["t0"] + timedelta(seconds=1)
    context["lookup_result"] = context["cache"].lookup(
        model_spec=model_spec, at=at
    )


@when(parsers.parse('查詢 "{model_spec}" at=T1+1sec'))
def lookup_t1(context, model_spec):
    at = context["t1"] + timedelta(seconds=1)
    context["lookup_result"] = context["cache"].lookup(
        model_spec=model_spec, at=at
    )


@then("應回傳 v1 的價格")
def assert_v1(context):
    assert context["lookup_result"]["input"] == pytest.approx(1.0)


@then("應回傳 v2 的價格")
def assert_v2(context):
    assert context["lookup_result"]["input"] == pytest.approx(2.0)


@when(
    parsers.parse(
        "管理員建立新版本 input={inp:g} effective_from=now+1sec 且呼叫 cache.refresh()"
    )
)
def add_new_version_and_refresh(context, inp):
    repo = context["repo"]
    at = _now() + timedelta(seconds=1)
    run(
        repo.save(
            ModelPricing(
                provider="openai",
                model_id="gpt-5",
                display_name="gpt-5",
                rate=PriceRate(inp, 5.0),
                effective_from=at,
                created_by="admin",
                note="bump",
            )
        )
    )
    run(context["cache"].refresh())
    context["new_effective_from"] = at


@then(parsers.parse('查詢 "{model_spec}" at=now+2sec 應回傳 input={inp:g}'))
def lookup_after_bump(context, model_spec, inp):
    at = _now() + timedelta(seconds=2)
    result = context["cache"].lookup(model_spec=model_spec, at=at)
    assert result is not None
    assert result["input"] == pytest.approx(inp)
