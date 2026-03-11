"""BDD Step Definitions — 診斷規則套用."""

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.observability.diagnostic import diagnose
from src.domain.observability.rule_config import DiagnosticRulesConfig

scenarios("unit/observability/diagnostic_rules_apply.feature")


@pytest.fixture()
def context():
    return {"dimensions": [], "config": None, "hints": []}


# -----------------------------------------------------------------------
# Given
# -----------------------------------------------------------------------


@given("自訂規則將 context_precision 門檻設為 0.6", target_fixture="context")
def custom_single_rule(context):
    context["config"] = DiagnosticRulesConfig(
        single_rules=[
            {
                "dimension": "context_precision", "threshold": 0.6,
                "category": "rag_strategy", "severity": "warning",
                "message": "自訂：精確度低於 0.6", "suggestion": "自訂建議",
            },
        ],
        combo_rules=[],
    )
    return context


@given("評估結果中 context_precision 分數為 0.5", target_fixture="context")
def eval_precision_score(context):
    context["dimensions"].append({"name": "context_precision", "score": 0.5})
    return context


@given("自訂交叉規則 precision > 0.7 且 recall <= 0.4 時觸發", target_fixture="context")
def custom_combo_rule(context):
    context["config"] = DiagnosticRulesConfig(
        single_rules=[],
        combo_rules=[
            {
                "dim_a": "context_precision", "op_a": ">", "threshold_a": 0.7,
                "dim_b": "context_recall", "op_b": "<=", "threshold_b": 0.4,
                "category": "rag_strategy", "severity": "warning",
                "dimension": "context_precision+context_recall",
                "message": "自訂交叉診斷", "suggestion": "增加 top_k",
            },
        ],
    )
    return context


@given("評估結果 precision 為 0.8 且 recall 為 0.3", target_fixture="context")
def eval_combo_scores(context):
    context["dimensions"] = [
        {"name": "context_precision", "score": 0.8},
        {"name": "context_recall", "score": 0.3},
    ]
    return context


# -----------------------------------------------------------------------
# When
# -----------------------------------------------------------------------


@when("執行診斷分析", target_fixture="context")
def run_diagnose(context):
    context["hints"] = diagnose(
        context["dimensions"],
        rule_config=context["config"],
    )
    return context


# -----------------------------------------------------------------------
# Then
# -----------------------------------------------------------------------


@then("應產生 warning 等級的診斷提示")
def verify_warning_hint(context):
    warnings = [h for h in context["hints"] if h.severity == "warning"]
    assert len(warnings) >= 1, f"Expected warning hint, got: {context['hints']}"


@then("應產生 rag_strategy 類別的交叉診斷提示")
def verify_combo_hint(context):
    matching = [h for h in context["hints"] if h.category == "rag_strategy"]
    assert len(matching) >= 1, f"Expected rag_strategy hint, got: {context['hints']}"
    assert "+" in matching[0].dimension, "Expected combo dimension"
