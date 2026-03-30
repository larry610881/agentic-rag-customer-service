"""Cache-Aware Token 計費 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.rag.pricing import calculate_usage
from src.domain.rag.value_objects import TokenUsage

scenarios("unit/usage/cache_aware_billing.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


# ── Given ──────────────────────────────────────────────────────

@given(
    parsers.parse(
        '模型 "{model}" 的定價為 input {inp:g} cache_read {cr:g} '
        "cache_creation {cc:g} output {out:g} per 1M tokens"
    ),
    target_fixture="context",
)
def setup_full_cache_pricing(context, model, inp, cr, cc, out):
    context["pricing"] = {
        model: {
            "input": inp,
            "output": out,
            "cache_read": cr,
            "cache_creation": cc,
        },
    }
    context["model"] = model
    return context


@given(
    parsers.parse(
        '模型 "{model}" 的定價為 input {inp:g} cache_read {cr:g} '
        "output {out:g} per 1M tokens"
    ),
    target_fixture="context",
)
def setup_cache_pricing_no_creation(context, model, inp, cr, out):
    context["pricing"] = {
        model: {
            "input": inp,
            "output": out,
            "cache_read": cr,
        },
    }
    context["model"] = model
    return context


@given("兩個含快取 tokens 的 TokenUsage 物件")
def setup_two_usages(context):
    context["usage_a"] = TokenUsage(
        model="test-model",
        input_tokens=100,
        output_tokens=50,
        total_tokens=250,
        estimated_cost=0.001,
        cache_read_tokens=80,
        cache_creation_tokens=20,
    )
    context["usage_b"] = TokenUsage(
        model="test-model",
        input_tokens=200,
        output_tokens=100,
        total_tokens=400,
        estimated_cost=0.002,
        cache_read_tokens=60,
        cache_creation_tokens=40,
    )


@given("一筆包含快取 tokens 的 TokenUsage")
def setup_usage_for_record(context):
    context["usage"] = TokenUsage(
        model="gpt-5.1",
        input_tokens=800,
        output_tokens=500,
        total_tokens=1500,
        estimated_cost=0.005,
        cache_read_tokens=150,
        cache_creation_tokens=50,
    )
    context["mock_repo"] = AsyncMock()


# ── When ───────────────────────────────────────────────────────

@when(
    parsers.parse(
        "計算 {inp:d} non-cached input、{cr:d} cache_read、"
        "{cc:d} cache_creation、{out:d} output tokens 的成本"
    ),
)
def do_calculate_with_cache(context, inp, cr, cc, out):
    context["usage"] = calculate_usage(
        model=context["model"],
        input_tokens=inp,
        output_tokens=out,
        pricing=context["pricing"],
        cache_read_tokens=cr,
        cache_creation_tokens=cc,
    )
    # Also calculate full-price (no cache) for comparison
    context["full_price_usage"] = calculate_usage(
        model=context["model"],
        input_tokens=inp + cr + cc,
        output_tokens=out,
        pricing=context["pricing"],
    )


@when("將兩個 usage 相加")
def add_usages(context):
    context["result"] = context["usage_a"] + context["usage_b"]


@when("執行 RecordUsageUseCase")
def execute_record_use_case(context):
    use_case = RecordUsageUseCase(usage_repository=context["mock_repo"])
    _run(use_case.execute(
        tenant_id="tenant-001",
        request_type="agent",
        usage=context["usage"],
    ))


# ── Then ───────────────────────────────────────────────────────

@then("estimated_cost 應低於無快取的全價計算")
def verify_cost_lower(context):
    assert context["usage"].estimated_cost < context["full_price_usage"].estimated_cost


@then("estimated_cost 應為各段費用之和")
def verify_anthropic_cost(context):
    u = context["usage"]
    p = context["pricing"][context["model"]]
    expected = (
        u.input_tokens * p["input"] / 1_000_000
        + u.cache_read_tokens * p["cache_read"] / 1_000_000
        + u.cache_creation_tokens * p["cache_creation"] / 1_000_000
        + u.output_tokens * p["output"] / 1_000_000
    )
    assert abs(u.estimated_cost - expected) < 1e-10


@then(parsers.parse("estimated_cost 應為 {expected:g}"))
def verify_exact_cost(context, expected):
    assert abs(context["usage"].estimated_cost - expected) < 1e-10


@then(parsers.parse("cache_read_tokens 應為 {expected:d}"))
def verify_cache_read_tokens(context, expected):
    usage = context.get("usage") or context.get("result")
    assert usage.cache_read_tokens == expected


@then(parsers.parse("cache_creation_tokens 應為 {expected:d}"))
def verify_cache_creation_tokens(context, expected):
    usage = context.get("usage") or context.get("result")
    assert usage.cache_creation_tokens == expected


@then("結果的 cache_read_tokens 應為兩者之和")
def verify_added_cache_read(context):
    expected = (
        context["usage_a"].cache_read_tokens
        + context["usage_b"].cache_read_tokens
    )
    assert context["result"].cache_read_tokens == expected


@then("結果的 cache_creation_tokens 應為兩者之和")
def verify_added_cache_creation(context):
    expected = (
        context["usage_a"].cache_creation_tokens
        + context["usage_b"].cache_creation_tokens
    )
    assert context["result"].cache_creation_tokens == expected


@then("儲存的 UsageRecord 應包含 cache_read_tokens 和 cache_creation_tokens")
def verify_saved_record(context):
    context["mock_repo"].save.assert_called_once()
    record = context["mock_repo"].save.call_args[0][0]
    assert record.cache_read_tokens == 150
    assert record.cache_creation_tokens == 50
