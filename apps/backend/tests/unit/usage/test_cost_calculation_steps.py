"""Token 成本計算 BDD Step Definitions"""

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.rag.pricing import calculate_usage

scenarios("unit/usage/cost_calculation.feature")


@pytest.fixture
def context():
    return {}


@given('模型 "claude-sonnet" 的定價為 input 3.0 output 15.0 per 1M tokens')
def setup_pricing(context):
    context["pricing"] = {
        "claude-sonnet": {"input": 3.0, "output": 15.0},
    }
    context["model"] = "claude-sonnet"


@given("空的定價表")
def setup_empty_pricing(context):
    context["pricing"] = {}
    context["model"] = "unknown-model"


@when("計算 100 input tokens 和 50 output tokens 的成本")
def do_calculate(context):
    context["usage"] = calculate_usage(
        model=context["model"],
        input_tokens=100,
        output_tokens=50,
        pricing=context["pricing"],
    )


@then("estimated_cost 應為 0.00105")
def verify_cost(context):
    # 100 * 3.0 / 1_000_000 + 50 * 15.0 / 1_000_000
    # = 0.0003 + 0.00075 = 0.00105
    assert abs(context["usage"].estimated_cost - 0.00105) < 1e-10


@then("estimated_cost 應為 0.0")
def verify_zero_cost(context):
    assert context["usage"].estimated_cost == 0.0
