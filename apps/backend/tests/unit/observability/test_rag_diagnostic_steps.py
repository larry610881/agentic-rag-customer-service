"""BDD Step Definitions — RAG Quality Diagnostic Engine."""

import pytest
from pytest_bdd import given, scenarios, then, when, parsers

from src.domain.observability.diagnostic import DiagnosticHint, diagnose

scenarios("unit/observability/rag_diagnostic.feature")


@pytest.fixture()
def context():
    return {"dimensions": [], "hints": []}


@given(
    parsers.parse("評估維度 {dim_name} 分數為 {score:f}"),
    target_fixture="context",
)
def add_dimension(context, dim_name: str, score: float):
    context["dimensions"].append({"name": dim_name, "score": score})
    return context


@when("執行診斷", target_fixture="context")
def run_diagnose(context):
    context["hints"] = diagnose(context["dimensions"])
    return context


@then(parsers.parse('應產生 category 為 "{category}" severity 為 "{severity}" 的提示'))
def verify_hint_category_severity(context, category: str, severity: str):
    matching = [h for h in context["hints"] if h.category == category and h.severity == severity]
    assert len(matching) >= 1, (
        f"Expected hint with category={category}, severity={severity}, "
        f"got: {[(h.category, h.severity) for h in context['hints']]}"
    )


@then(parsers.parse('應包含建議 "{keyword}"'))
def verify_suggestion_keyword(context, keyword: str):
    all_suggestions = " ".join(h.suggestion for h in context["hints"])
    assert keyword in all_suggestions, (
        f"Expected '{keyword}' in suggestions, got: {all_suggestions}"
    )


@then("診斷結果為空")
def verify_empty_hints(context):
    assert len(context["hints"]) == 0, (
        f"Expected no hints, got {len(context['hints'])}: "
        f"{[(h.category, h.dimension, h.message) for h in context['hints']]}"
    )
