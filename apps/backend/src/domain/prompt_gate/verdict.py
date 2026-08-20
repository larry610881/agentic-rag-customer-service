"""Gate Verdict Engine — 分層判定純函式（spec §2.3/§4.4）

    通過 = 硬閘門通過率 100%
         AND 軟閘門通過率 ≥ 門檻（bot 級可調，預設 0.8）
         AND 驗證成本 ≤ 預算上限

聚合一律以 case_id 對齊（防「只重跑 P0 子集」下的 by-index 靜默錯位，
spec §7.3 探索發現 validation_evaluator.py:57 的隱性契約問題）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# case 級軟通過門檻（沿用 prompt_optimizer/evaluator.py 的 VALIDATION_THRESHOLDS
# 現值；fence 測試保證兩處一致）
PRIORITY_THRESHOLDS: dict[str, float] = {"P0": 1.0, "P1": 0.8, "P2": 0.6}
_DEFAULT_THRESHOLD = 0.6

FAIL_HARD_GATE = "hard_gate"
FAIL_SOFT_GATE = "soft_gate"
FAIL_BUDGET = "budget_exceeded"


@dataclass(frozen=True)
class AssertionOutcome:
    type: str
    severity: str  # hard | soft（由 assertion_severity.resolve_severity 決定）
    passed: bool
    message: str = ""


@dataclass(frozen=True)
class CaseRoundResult:
    """單一 case 單一輪次的評測結果（gate runner 的原子輸出）。"""

    case_id: str
    priority: str  # P0 | P1 | P2
    round_index: int
    assertions: tuple[AssertionOutcome, ...] = ()


@dataclass(frozen=True)
class CaseAggregate:
    case_id: str
    priority: str
    total_rounds: int
    hard_failed: bool
    has_soft: bool
    soft_pass_rate: float  # 軟斷言全過的輪次比例（無軟斷言 = 1.0）
    soft_passed: bool      # soft_pass_rate ≥ PRIORITY_THRESHOLDS[priority]
    unstable: bool         # 軟通過但非每輪全過


@dataclass(frozen=True)
class GateVerdict:
    passed: bool
    fail_reasons: tuple[str, ...]
    total_cases: int
    hard_failed_cases: int
    soft_pass_rate: float  # 軟通過案例數 / 含軟斷言案例數（分母 0 = 1.0）
    unstable_cases: int
    cases: dict[str, CaseAggregate] = field(default_factory=dict)


def aggregate_cases(
    rounds: list[CaseRoundResult],
) -> dict[str, CaseAggregate]:
    """以 case_id 分組聚合多輪結果（輸入順序無關）。"""
    by_case: dict[str, list[CaseRoundResult]] = {}
    for r in rounds:
        by_case.setdefault(r.case_id, []).append(r)

    aggregates: dict[str, CaseAggregate] = {}
    for case_id, case_rounds in by_case.items():
        priority = case_rounds[0].priority
        hard_failed = any(
            not a.passed
            for r in case_rounds
            for a in r.assertions
            if a.severity == "hard"
        )
        has_soft = any(
            a.severity == "soft" for r in case_rounds for a in r.assertions
        )
        if has_soft:
            soft_ok_rounds = sum(
                1
                for r in case_rounds
                if all(
                    a.passed for a in r.assertions if a.severity == "soft"
                )
            )
            soft_pass_rate = soft_ok_rounds / len(case_rounds)
        else:
            soft_pass_rate = 1.0
        threshold = PRIORITY_THRESHOLDS.get(priority, _DEFAULT_THRESHOLD)
        soft_passed = soft_pass_rate >= threshold
        aggregates[case_id] = CaseAggregate(
            case_id=case_id,
            priority=priority,
            total_rounds=len(case_rounds),
            hard_failed=hard_failed,
            has_soft=has_soft,
            soft_pass_rate=soft_pass_rate,
            soft_passed=soft_passed,
            unstable=has_soft and soft_passed and soft_pass_rate < 1.0,
        )
    return aggregates


def compute_verdict(
    aggregates: dict[str, CaseAggregate],
    *,
    soft_threshold: float,
    budget_usd: float,
    actual_cost: float,
) -> GateVerdict:
    hard_failed_cases = sum(1 for a in aggregates.values() if a.hard_failed)
    soft_cases = [a for a in aggregates.values() if a.has_soft]
    if soft_cases:
        soft_pass_rate = sum(1 for a in soft_cases if a.soft_passed) / len(
            soft_cases
        )
    else:
        soft_pass_rate = 1.0

    reasons: list[str] = []
    if hard_failed_cases > 0:
        reasons.append(FAIL_HARD_GATE)
    if soft_pass_rate < soft_threshold:
        reasons.append(FAIL_SOFT_GATE)
    if actual_cost > budget_usd:
        reasons.append(FAIL_BUDGET)

    return GateVerdict(
        passed=not reasons,
        fail_reasons=tuple(reasons),
        total_cases=len(aggregates),
        hard_failed_cases=hard_failed_cases,
        soft_pass_rate=soft_pass_rate,
        unstable_cases=sum(1 for a in aggregates.values() if a.unstable),
        cases=aggregates,
    )
