"""BDD Step Definitions — 診斷規則 CRUD."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.observability.diagnostic_rules_use_cases import (
    GetDiagnosticRulesUseCase,
    ResetDiagnosticRulesUseCase,
    UpdateDiagnosticRulesCommand,
    UpdateDiagnosticRulesUseCase,
)
from src.domain.observability.diagnostic import (
    get_default_single_rules,
)
from src.domain.observability.rule_config import (
    DiagnosticRulesConfig,
    DiagnosticRulesConfigRepository,
)

scenarios("unit/observability/diagnostic_rules_crud.feature")


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@pytest.fixture()
def context():
    return {}


# -----------------------------------------------------------------------
# Given
# -----------------------------------------------------------------------


@given("DB 中已儲存自訂診斷規則", target_fixture="context")
def db_has_custom_rules(context):
    custom_rules = [
        {
            "dimension": "context_precision", "threshold": 0.3,
            "category": "data_source", "severity": "critical",
            "message": "自訂訊息", "suggestion": "自訂建議",
        },
    ]
    config = DiagnosticRulesConfig(
        single_rules=custom_rules,
        combo_rules=[],
    )
    repo = AsyncMock(spec=DiagnosticRulesConfigRepository)
    repo.get.return_value = config
    repo.save.return_value = None
    repo.delete.return_value = None
    context["repo"] = repo
    context["config"] = config
    return context


@given("DB 中沒有診斷規則", target_fixture="context")
def db_has_no_rules(context):
    repo = AsyncMock(spec=DiagnosticRulesConfigRepository)
    repo.get.return_value = None
    context["repo"] = repo
    return context


# -----------------------------------------------------------------------
# When
# -----------------------------------------------------------------------


@when("我取得診斷規則", target_fixture="result")
def get_rules(context):
    uc = GetDiagnosticRulesUseCase(
        diagnostic_rules_config_repository=context["repo"],
    )
    return _run(uc.execute())


@when("我更新 context_precision 的門檻為 0.4", target_fixture="result")
def update_rules(context):
    new_rules = [
        {
            "dimension": "context_precision", "threshold": 0.4,
            "category": "data_source", "severity": "critical",
            "message": "更新後訊息", "suggestion": "更新後建議",
        },
    ]
    uc = UpdateDiagnosticRulesUseCase(
        diagnostic_rules_config_repository=context["repo"],
    )
    return _run(uc.execute(UpdateDiagnosticRulesCommand(
        single_rules=new_rules,
        combo_rules=[],
    )))


@when("我還原為預設規則", target_fixture="result")
def reset_rules(context):
    uc = ResetDiagnosticRulesUseCase(
        diagnostic_rules_config_repository=context["repo"],
    )
    return _run(uc.execute())


# -----------------------------------------------------------------------
# Then
# -----------------------------------------------------------------------


@then("應回傳 DB 中的規則")
def verify_db_rules(result):
    assert result.single_rules[0]["message"] == "自訂訊息"


@then("應回傳系統預設規則")
def verify_default_rules(result):
    assert len(result.single_rules) > 0
    assert result.single_rules[0]["dimension"] == "context_precision"


@then("單維度規則數量應為 10")
def verify_single_rules_count(result):
    assert len(result.single_rules) == len(get_default_single_rules())


@then("儲存應成功")
def verify_save_called(context):
    context["repo"].save.assert_called_once()


@then("更新後的規則應反映新門檻")
def verify_updated_threshold(result):
    assert result.single_rules[0]["threshold"] == 0.4


@then("規則應回到系統預設值")
def verify_reset_to_defaults(result, context):
    context["repo"].delete.assert_called_once()
    defaults = get_default_single_rules()
    assert len(result.single_rules) == len(defaults)
    assert result.single_rules[0]["dimension"] == defaults[0]["dimension"]
