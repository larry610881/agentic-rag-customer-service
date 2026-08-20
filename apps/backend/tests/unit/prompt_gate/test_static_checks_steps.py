"""第 0 層靜態檢查 BDD Step Definitions"""

from pytest_bdd import parsers, scenarios, then, when

from src.application.prompt_gate.static_checks import check_prompt

scenarios("unit/prompt_gate/static_checks.feature")


@when(parsers.parse('靜態檢查 prompt "{text}"'), target_fixture="result")
def check_text(text):
    return check_prompt(text)


@when("靜態檢查一個 40000 字元的 prompt", target_fixture="result")
def check_long_text():
    return check_prompt("你是客服。" + "很" * 39995)


@when("靜態檢查空白 prompt", target_fixture="result")
def check_empty():
    return check_prompt("")


@then("檢查通過且無違規")
def verify_passed(result):
    assert result.passed, f"預期通過，實際違規: {result.violations}"


@then(parsers.parse("檢查失敗且違規類型為 {vtype}"))
def verify_failed_with_type(result, vtype):
    assert not result.passed
    assert any(v.type == vtype for v in result.violations), (
        f"預期違規類型 {vtype}，實際: {result.violations}"
    )


@then('違規明細指出 "{user_name}"')
def verify_detail_mentions_var(result):
    assert any("user_name" in v.detail for v in result.violations)


@then("檢查失敗且違規包含 injection_phrase 與 unknown_variable")
def verify_multiple_violations(result):
    types = {v.type for v in result.violations}
    assert {"injection_phrase", "unknown_variable"} <= types
