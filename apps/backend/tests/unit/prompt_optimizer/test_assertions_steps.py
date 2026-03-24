"""Prompt Optimizer 二元斷言庫 BDD Step Definitions"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from prompt_optimizer.assertions import (
    ASSERTION_REGISTRY,
    AssertionContext,
    AssertionResult,
    run_assertion,
)

scenarios("unit/prompt_optimizer/assertions.feature")


@pytest.fixture
def context():
    return {}


# ═══════════════════════════════════════════════════════════════
# Given steps
# ═══════════════════════════════════════════════════════════════


@given(parsers.parse('回應文字為 "{text}"'))
def given_response_text(context, text):
    context["ctx"] = AssertionContext(response_text=text)


@given(parsers.parse("回應延遲為 {ms:d} 毫秒"))
def given_latency(context, ms):
    context["ctx"] = AssertionContext(response_text="", latency_ms=ms)


@given(parsers.parse("回應包含 {count:d} 個來源"))
def given_sources(context, count):
    sources = [{"id": f"src-{i}", "score": 0.9} for i in range(count)]
    context["ctx"] = AssertionContext(response_text="", sources=sources)


@given(parsers.parse('工具呼叫包含 "{tool_name}"'))
def given_tool_calls(context, tool_name):
    context["ctx"] = AssertionContext(
        response_text="",
        tool_calls=[{"tool_name": tool_name, "args": "{}"}],
    )


@given(parsers.parse("回應使用 {tokens:d} 個 token"))
def given_tokens(context, tokens):
    context["ctx"] = AssertionContext(
        response_text="", total_tokens=tokens,
    )


@given(parsers.parse("回應成本為 {cost:f}"))
def given_cost(context, cost):
    context["ctx"] = AssertionContext(
        response_text="", estimated_cost=cost,
    )


# ═══════════════════════════════════════════════════════════════
# When steps — Format
# ═══════════════════════════════════════════════════════════════


@when(
    parsers.parse("執行 max_length 斷言，max_chars 為 {max_chars:d}"),
    target_fixture="result",
)
def when_max_length(context, max_chars):
    return run_assertion("max_length", context["ctx"], {"max_chars": max_chars})


@when(
    parsers.parse("執行 min_length 斷言，min_chars 為 {min_chars:d}"),
    target_fixture="result",
)
def when_min_length(context, min_chars):
    return run_assertion("min_length", context["ctx"], {"min_chars": min_chars})


@when(
    parsers.parse('執行 language_match 斷言，expected 為 "{expected}"'),
    target_fixture="result",
)
def when_language_match(context, expected):
    return run_assertion("language_match", context["ctx"], {"expected": expected})


@when(
    parsers.parse("執行 latency_under 斷言，max_ms 為 {max_ms:d}"),
    target_fixture="result",
)
def when_latency_under(context, max_ms):
    return run_assertion("latency_under", context["ctx"], {"max_ms": max_ms})


# ═══════════════════════════════════════════════════════════════
# When steps — Content
# ═══════════════════════════════════════════════════════════════


@when(
    parsers.parse('執行 contains_any 斷言，keywords 為 "{kw_str}"'),
    target_fixture="result",
)
def when_contains_any(context, kw_str):
    keywords = [k.strip() for k in kw_str.split(",")]
    return run_assertion("contains_any", context["ctx"], {"keywords": keywords})


@when(
    parsers.parse('執行 contains_all 斷言，keywords 為 "{kw_str}"'),
    target_fixture="result",
)
def when_contains_all(context, kw_str):
    keywords = [k.strip() for k in kw_str.split(",")]
    return run_assertion("contains_all", context["ctx"], {"keywords": keywords})


@when(
    parsers.parse('執行 not_contains 斷言，keywords 為 "{kw_str}"'),
    target_fixture="result",
)
def when_not_contains(context, kw_str):
    keywords = [k.strip() for k in kw_str.split(",")]
    return run_assertion("not_contains", context["ctx"], {"keywords": keywords})


@when("執行 no_hallucination_markers 斷言", target_fixture="result")
def when_no_hallucination_markers(context):
    return run_assertion("no_hallucination_markers", context["ctx"], {})


@when(
    parsers.parse("執行 has_citations 斷言，min_count 為 {min_count:d}"),
    target_fixture="result",
)
def when_has_citations(context, min_count):
    return run_assertion("has_citations", context["ctx"], {"min_count": min_count})


# ═══════════════════════════════════════════════════════════════
# When steps — Behavior
# ═══════════════════════════════════════════════════════════════


@when(
    parsers.parse('執行 tool_was_called 斷言，tool_name 為 "{tool_name}"'),
    target_fixture="result",
)
def when_tool_was_called(context, tool_name):
    return run_assertion("tool_was_called", context["ctx"], {"tool_name": tool_name})


@when(
    parsers.parse('執行 tool_not_called 斷言，tool_name 為 "{tool_name}"'),
    target_fixture="result",
)
def when_tool_not_called(context, tool_name):
    return run_assertion("tool_not_called", context["ctx"], {"tool_name": tool_name})


@when("執行 refused_gracefully 斷言", target_fixture="result")
def when_refused_gracefully(context):
    return run_assertion("refused_gracefully", context["ctx"], {})


# ═══════════════════════════════════════════════════════════════
# When steps — Quality + Cost
# ═══════════════════════════════════════════════════════════════


@when("執行 response_not_empty 斷言", target_fixture="result")
def when_response_not_empty(context):
    return run_assertion("response_not_empty", context["ctx"], {})


@when(
    parsers.parse("執行 token_count_under 斷言，max_tokens 為 {max_tokens:d}"),
    target_fixture="result",
)
def when_token_count_under(context, max_tokens):
    return run_assertion("token_count_under", context["ctx"], {"max_tokens": max_tokens})


@when(
    parsers.parse("執行 cost_under 斷言，max_cost 為 {max_cost:f}"),
    target_fixture="result",
)
def when_cost_under(context, max_cost):
    return run_assertion("cost_under", context["ctx"], {"max_cost": max_cost})


# ═══════════════════════════════════════════════════════════════
# When steps — Security
# ═══════════════════════════════════════════════════════════════


@when(
    parsers.parse('執行 no_system_prompt_leak 斷言，prompt_fragments 為 "{fragments_str}"'),
    target_fixture="result",
)
def when_no_system_prompt_leak(context, fragments_str):
    fragments = [f.strip() for f in fragments_str.split(",")]
    return run_assertion(
        "no_system_prompt_leak", context["ctx"], {"prompt_fragments": fragments}
    )


@when("執行 no_role_switch 斷言", target_fixture="result")
def when_no_role_switch(context):
    return run_assertion("no_role_switch", context["ctx"], {})


@when("執行 no_pii_leak 斷言", target_fixture="result")
def when_no_pii_leak(context):
    return run_assertion("no_pii_leak", context["ctx"], {})


# ═══════════════════════════════════════════════════════════════
# Then steps
# ═══════════════════════════════════════════════════════════════


@then("斷言應通過")
def then_passed(result):
    assert result.passed is True, f"Expected pass but got fail: {result.message}"


@then("斷言應失敗")
def then_failed(result):
    assert result.passed is False, f"Expected fail but got pass: {result.message}"


@then(parsers.parse('失敗訊息應包含 "{text}"'))
def then_message_contains(result, text):
    assert text in result.message, f"Expected '{text}' in '{result.message}'"
