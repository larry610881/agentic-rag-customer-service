"""Gate Verdict Engine BDD Step Definitions（純 domain，無 mock）"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.prompt_gate.assertion_severity import resolve_severity
from src.domain.prompt_gate.verdict import (
    FAIL_BUDGET,
    FAIL_HARD_GATE,
    FAIL_SOFT_GATE,
    AssertionOutcome,
    CaseRoundResult,
    aggregate_cases,
    compute_verdict,
)

scenarios("unit/prompt_gate/gate_verdict.feature")


def _hard(passed: bool) -> AssertionOutcome:
    return AssertionOutcome(
        type="no_role_switch", severity="hard", passed=passed
    )


def _soft(passed: bool) -> AssertionOutcome:
    return AssertionOutcome(
        type="contains_all", severity="soft", passed=passed
    )


def _round(case_id, priority, idx, assertions):
    return CaseRoundResult(
        case_id=case_id, priority=priority, round_index=idx,
        assertions=tuple(assertions),
    )


def _uniform_rounds(*, n_soft_pass: int, n_soft_total: int, hard_fail_one: bool):
    """組一組結果：10 個軟案例（其中 n_soft_pass 個通過），
    hard_fail_one 時額外一個硬失敗案例。全部單輪。"""
    rounds = []
    for i in range(n_soft_total):
        rounds.append(
            _round(f"soft-{i}", "P1", 0, [_hard(True), _soft(i < n_soft_pass)])
        )
    if hard_fail_one:
        rounds.append(_round("hard-x", "P0", 0, [_hard(False), _soft(True)]))
    return rounds


@pytest.fixture
def context():
    return {}


# ─── Given：整組結果 ───


@given(parsers.parse(
    "一組 gate 評測結果：硬斷言全過、軟通過率 {rate:g}、成本 {cost:g}"
))
def results_soft_rate(context, rate, cost):
    # 用 1000 個案例逼近任意比率（0.799 → 799/1000）
    total = 1000
    context["rounds"] = _uniform_rounds(
        n_soft_pass=round(rate * total), n_soft_total=total,
        hard_fail_one=False,
    )
    context["cost"] = cost


@given(parsers.parse(
    "一組 gate 評測結果：1 個 case 硬斷言失敗、軟通過率 {rate:g}、成本 {cost:g}"
))
def results_with_hard_fail(context, rate, cost):
    total = 10
    context["rounds"] = _uniform_rounds(
        n_soft_pass=round(rate * total), n_soft_total=total,
        hard_fail_one=True,
    )
    context["cost"] = cost


@given("一組結果：2 個案例只有硬斷言且全過、1 個案例軟斷言全過")
def results_hard_only(context):
    context["rounds"] = [
        _round("h1", "P0", 0, [_hard(True)]),
        _round("h2", "P0", 0, [_hard(True)]),
        _round("s1", "P1", 0, [_soft(True)]),
    ]
    context["cost"] = 0.1


# ─── Given：單一案例多輪 ───


@given(parsers.parse('P0 案例 "{cid}" 三輪結果中第二輪硬斷言失敗'))
def p0_hard_fail_round2(context, cid):
    context["rounds"] = [
        _round(cid, "P0", 0, [_hard(True), _soft(True)]),
        _round(cid, "P0", 1, [_hard(False), _soft(True)]),
        _round(cid, "P0", 2, [_hard(True), _soft(True)]),
    ]
    context["cid"] = cid


@given(parsers.parse('P2 案例 "{cid}" 三輪結果中軟斷言通過兩輪'))
def p2_soft_two_of_three(context, cid):
    context["rounds"] = [
        _round(cid, "P2", 0, [_soft(True)]),
        _round(cid, "P2", 1, [_soft(False)]),
        _round(cid, "P2", 2, [_soft(True)]),
    ]
    context["cid"] = cid


@given(parsers.parse('P1 案例 "{cid}" 三輪結果中軟斷言通過兩輪'))
def p1_soft_two_of_three(context, cid):
    context["rounds"] = [
        _round(cid, "P1", 0, [_soft(True)]),
        _round(cid, "P1", 1, [_soft(False)]),
        _round(cid, "P1", 2, [_soft(True)]),
    ]
    context["cid"] = cid


@given("三個案例的多輪結果以亂序輸入")
def shuffled_rounds(context):
    # c-a：軟 2/3 過；c-b：全過；c-c：軟 0/2 過 —— 刻意交錯排列
    context["rounds"] = [
        _round("c-b", "P1", 0, [_soft(True)]),
        _round("c-a", "P1", 2, [_soft(True)]),
        _round("c-c", "P2", 1, [_soft(False)]),
        _round("c-a", "P1", 0, [_soft(True)]),
        _round("c-b", "P1", 1, [_soft(True)]),
        _round("c-a", "P1", 1, [_soft(False)]),
        _round("c-c", "P2", 0, [_soft(False)]),
    ]


@given(parsers.parse(
    '案例 "{cid}" 的 contains_all 斷言 params 帶 severity hard 且失敗'
))
def severity_override_case(context, cid):
    severity = resolve_severity("contains_all", {"severity": "hard"})
    context["rounds"] = [
        _round(cid, "P1", 0, [
            AssertionOutcome(
                type="contains_all", severity=severity, passed=False
            )
        ])
    ]
    context["cid"] = cid


# ─── When ───


@when(parsers.parse("以軟門檻 {threshold:g} 與預算 {budget:g} 判定"))
def do_verdict(context, threshold, budget):
    aggregates = aggregate_cases(context["rounds"])
    context["verdict"] = compute_verdict(
        aggregates,
        soft_threshold=threshold,
        budget_usd=budget,
        actual_cost=context["cost"],
    )


@when("聚合該案例")
@when("聚合全部案例")
def do_aggregate(context):
    context["aggregates"] = aggregate_cases(context["rounds"])


# ─── Then ───


@then("判定為 PASS 且無失敗原因")
def verify_pass(context):
    v = context["verdict"]
    assert v.passed, f"預期 PASS，實際 fail_reasons={v.fail_reasons}"
    assert v.fail_reasons == ()


@then(parsers.re(r"判定為 FAIL 且失敗原因含 (?P<reason>[a-z_]+)$"))
def verify_fail_reason(context, reason):
    v = context["verdict"]
    assert not v.passed
    assert reason in v.fail_reasons


@then("判定為 FAIL 且失敗原因含 hard_gate 與 soft_gate 與 budget_exceeded")
def verify_all_reasons(context):
    v = context["verdict"]
    assert not v.passed
    assert set(v.fail_reasons) == {
        FAIL_HARD_GATE, FAIL_SOFT_GATE, FAIL_BUDGET,
    }


@then("硬失敗案例數為 1")
def verify_hard_count(context):
    assert context["verdict"].hard_failed_cases == 1


@then(parsers.parse('案例 "{cid}" 標記為硬失敗'))
def verify_case_hard_failed(context, cid):
    assert context["aggregates"][cid].hard_failed is True


@then(parsers.parse('案例 "{cid}" 軟通過且標記 unstable'))
def verify_case_unstable(context, cid):
    agg = context["aggregates"][cid]
    assert agg.soft_passed is True  # P2 門檻 0.6，2/3 ≈ 0.667 通過
    assert agg.unstable is True


@then(parsers.parse('案例 "{cid}" 軟未通過'))
def verify_case_soft_failed(context, cid):
    agg = context["aggregates"][cid]
    assert agg.soft_passed is False  # P1 門檻 0.8，2/3 < 0.8
    assert agg.hard_failed is False


@then("判定為 PASS 且軟通過率為 1.0")
def verify_pass_soft_rate_one(context):
    v = context["verdict"]
    assert v.passed
    assert v.soft_pass_rate == 1.0


@then("每個案例的通過率與自身輪次一致")
def verify_by_id_alignment(context):
    aggs = context["aggregates"]
    assert aggs["c-a"].soft_pass_rate == pytest.approx(2 / 3)
    assert aggs["c-a"].total_rounds == 3
    assert aggs["c-b"].soft_pass_rate == 1.0
    assert aggs["c-b"].total_rounds == 2
    assert aggs["c-c"].soft_pass_rate == 0.0
    assert aggs["c-c"].total_rounds == 2
