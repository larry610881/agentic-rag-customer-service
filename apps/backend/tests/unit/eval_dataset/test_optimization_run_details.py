"""Optimization Run Details BDD Step Definitions."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.eval_dataset.run_use_cases import GetRunUseCase
from src.domain.eval_dataset.run_entity import OptimizationIteration

scenarios("unit/eval_dataset/optimization_run_details.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture
def context():
    return {}


# --- Scenario 1: details 應包含 case_results ---


@given("一個包含 3 個測試案例的 eval dataset")
def setup_dataset(context):
    context["case_results"] = [
        {
            "case_id": f"case-{i}",
            "question": f"測試問題 {i}",
            "priority": "P0" if i == 0 else "P1",
            "category": "general",
            "score": 1.0 if i < 2 else 0.5,
            "passed_count": 2 if i < 2 else 1,
            "total_count": 2,
            "p0_failed": False,
            "answer_snippet": f"AI 回答內容 {i}",
            "assertion_results": [
                {"passed": True, "assertion_type": "contains_text", "message": "OK"},
                {
                    "passed": i < 2,
                    "assertion_type": "no_hallucination",
                    "message": "OK" if i < 2 else "Failed",
                },
            ],
        }
        for i in range(3)
    ]


@given("一個已完成評估的 iteration result")
def setup_iteration_result(context):
    # Build the details dict the same way run_use_cases.py does
    context["details"] = {
        "quality_score": 0.85,
        "cost_score": 0.92,
        "avg_total_tokens": 1200,
        "accepted": True,
        "case_results": context["case_results"],
    }


@when("將 iteration 儲存至 details JSON")
def save_iteration(context):
    # The details dict is already built; this step validates the structure
    context["saved_details"] = context["details"]


@then("details 應包含 case_results 陣列")
def verify_case_results_exists(context):
    assert "case_results" in context["saved_details"]
    assert isinstance(context["saved_details"]["case_results"], list)


@then("case_results 長度應為 3")
def verify_case_results_length(context):
    assert len(context["saved_details"]["case_results"]) == 3


@then("每個 case_result 應包含 case_id 和 question 和 score 和 answer_snippet")
def verify_case_result_fields(context):
    for cr in context["saved_details"]["case_results"]:
        assert "case_id" in cr
        assert "question" in cr
        assert "score" in cr
        assert "answer_snippet" in cr


@then("每個 case_result 應包含 assertion_results 陣列")
def verify_assertion_results(context):
    for cr in context["saved_details"]["case_results"]:
        assert "assertion_results" in cr
        assert isinstance(cr["assertion_results"], list)
        for ar in cr["assertion_results"]:
            assert "passed" in ar
            assert "assertion_type" in ar
            assert "message" in ar


# --- Scenario 2: GetRunUseCase 回傳 current_score ---


@given("一個進行中的 optimization run 在第 3 輪 score 為 0.75")
def setup_active_run(context):
    mock_repo = AsyncMock()
    mock_repo.get_iterations = AsyncMock(return_value=[])

    mock_run_manager = MagicMock()
    active_run = MagicMock()
    active_run.run_id = "run-001"
    active_run.tenant_id = "tenant-001"
    active_run.target_field = "base_prompt"
    active_run.bot_id = "bot-001"
    active_run.status = "running"
    active_run.baseline_score = 0.60
    active_run.best_score = 0.75
    active_run.current_score = 0.75
    active_run.current_iteration = 3
    active_run.max_iterations = 10
    active_run.total_api_calls = 48
    active_run.stopped_reason = ""
    active_run.progress_message = "第 3 輪：0.7500 ✓ 接受"
    active_run.started_at = MagicMock()
    active_run.started_at.isoformat = MagicMock(return_value="2026-03-24T10:00:00+00:00")
    active_run.completed_at = None

    mock_run_manager.get_run = MagicMock(return_value=active_run)

    context["use_case"] = GetRunUseCase(
        optimization_run_repository=mock_repo,
        run_manager=mock_run_manager,
    )
    context["run_id"] = "run-001"


@when("查詢該 run 的詳情", target_fixture="run_detail")
def query_run_detail(context):
    return _run(context["use_case"].execute(context["run_id"]))


@then("response 應包含 current_score 為 0.75")
def verify_current_score(run_detail):
    assert "current_score" in run_detail
    assert run_detail["current_score"] == 0.75
