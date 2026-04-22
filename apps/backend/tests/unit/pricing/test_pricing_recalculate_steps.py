"""BDD step defs — unit/pricing/pricing_recalculate.feature"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.pricing.dry_run_recalculate_use_case import (
    DryRunRecalculateCommand,
    DryRunRecalculateUseCase,
)
from src.application.pricing.execute_recalculate_use_case import (
    ExecuteRecalculateCommand,
    ExecuteRecalculateUseCase,
)
from src.domain.pricing.entity import ModelPricing
from src.domain.pricing.repository import UsageRecalcRow
from src.domain.pricing.value_objects import PriceRate
from tests.unit.pricing.conftest import (
    FakeAuditRepo,
    FakeCache,
    FakeModelPricingRepo,
    FakeUsageRecalcPort,
    run,
)

scenarios("unit/pricing/pricing_recalculate.feature")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@given(
    parsers.parse(
        'token_usage_records 有 {n:d} 筆 "{prefix}:{model_id}" usage 在過去 1 小時'
    )
)
def seed_usage(context, n, prefix, model_id):
    context["usage_rows"] = [
        UsageRecalcRow(
            id=f"row-{i}",
            model=f"{prefix}:{model_id}",
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            estimated_cost=0.0035,  # 稍後 "And 每筆 estimated_cost=..." 會覆蓋
        )
        for i in range(n)
    ]
    context["prefix"] = prefix
    context["model_id"] = model_id


@given(
    parsers.parse(
        "每筆 input_tokens={it:d} output_tokens={ot:d} estimated_cost={cost:g}"
    )
)
def set_usage_fields(context, it, ot, cost):
    context["usage_rows"] = [
        UsageRecalcRow(
            id=r.id,
            model=r.model,
            input_tokens=it,
            output_tokens=ot,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            estimated_cost=cost,
        )
        for r in context["usage_rows"]
    ]


@given(
    parsers.parse("已建立新版本 pricing input={inp:g} output={out:g}")
)
def set_new_pricing(context, inp, out):
    _build_pricing_and_deps(context, inp, out)


@given(parsers.parse("token_usage_records 在區間內有 {n:d} 筆符合"))
def seed_large_usage(context, n):
    context["usage_rows"] = [
        UsageRecalcRow(
            id=f"row-{i}",
            model="anthropic:claude-haiku-4-5",
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            estimated_cost=0.0035,
        )
        for i in range(n)
    ]
    context["prefix"] = "anthropic"
    context["model_id"] = "claude-haiku-4-5"
    _build_pricing_and_deps(context, 1.10, 5.50)


def _build_pricing_and_deps(context, inp, out):
    pricing_repo = FakeModelPricingRepo()
    p = ModelPricing(
        id="pricing-1",
        provider=context["prefix"],
        model_id=context["model_id"],
        display_name=context["model_id"],
        rate=PriceRate(inp, out),
        effective_from=_now() - timedelta(hours=2),
        created_by="admin",
        note="bump",
    )
    run(pricing_repo.save(p))
    context["pricing_repo"] = pricing_repo
    context["pricing"] = p
    context["audit_repo"] = FakeAuditRepo()
    context["usage_port"] = FakeUsageRecalcPort(context["usage_rows"])
    context["cache"] = FakeCache()


@when("我以該 pricing 對「過去 1 小時」區間 dry-run")
def dry_run(context):
    uc = DryRunRecalculateUseCase(
        pricing_repo=context["pricing_repo"],
        usage_port=context["usage_port"],
        cache=context["cache"],
    )
    try:
        result = run(
            uc.execute(
                DryRunRecalculateCommand(
                    pricing_id=context["pricing"].id,
                    recalc_from=_now() - timedelta(hours=1),
                    recalc_to=_now(),
                    actor="admin",
                )
            )
        )
        context["dry_run"] = result
    except Exception as exc:
        context["error"] = exc


@when("我對該區間 dry-run")
def dry_run_large(context):
    dry_run(context)


@when("我執行 recalculate execute 不帶 dry_run_token")
def execute_no_token(context):
    _build_pricing_and_deps_if_missing(context)
    uc = ExecuteRecalculateUseCase(
        pricing_repo=context["pricing_repo"],
        audit_repo=context["audit_repo"],
        usage_port=context["usage_port"],
        cache=context["cache"],
    )
    try:
        run(
            uc.execute(
                ExecuteRecalculateCommand(
                    dry_run_token="",
                    reason="should fail",
                    actor="admin",
                )
            )
        )
    except Exception as exc:
        context["error"] = exc


@given("已取得 dry_run_token 但 TTL 已過期")
def token_expired(context):
    # 建立最小 pricing deps，並手動塞一個過期 token
    context["usage_rows"] = []
    context["prefix"] = "anthropic"
    context["model_id"] = "claude-haiku-4-5"
    _build_pricing_and_deps(context, 1.0, 5.0)
    context["expired_token"] = "expired-uuid-xyz"
    # Cache 沒存 → 取出來會是 None → 視同過期


@when("我用該 token 執行 recalculate execute")
def execute_expired_token(context):
    uc = ExecuteRecalculateUseCase(
        pricing_repo=context["pricing_repo"],
        audit_repo=context["audit_repo"],
        usage_port=context["usage_port"],
        cache=context["cache"],
    )
    try:
        run(
            uc.execute(
                ExecuteRecalculateCommand(
                    dry_run_token=context["expired_token"],
                    reason="補算",
                    actor="admin",
                )
            )
        )
    except Exception as exc:
        context["error"] = exc


@given(parsers.parse("dry-run 回傳 affected_rows={n:d}"))
def dry_run_rows_given(context, n):
    # 先建立場景：N 筆 usage + pricing + 跑 dry-run
    if "usage_rows" not in context or len(context["usage_rows"]) != n:
        context["prefix"] = "anthropic"
        context["model_id"] = "claude-haiku-4-5"
        context["usage_rows"] = [
            UsageRecalcRow(
                id=f"row-{i}",
                model="anthropic:claude-haiku-4-5",
                input_tokens=1000,
                output_tokens=500,
                cache_read_tokens=0,
                cache_creation_tokens=0,
                estimated_cost=0.0035,
            )
            for i in range(n)
        ]
        _build_pricing_and_deps(context, 1.10, 5.50)
    dry_run(context)


@given(parsers.parse("dry-run 之後 token_usage_records 又多了 {n:d} 筆符合條件的 row"))
def add_rows_after_dry_run(context, n):
    base = len(context["usage_port"]._rows)
    new_rows = list(context["usage_port"]._rows) + [
        UsageRecalcRow(
            id=f"new-{i}",
            model="anthropic:claude-haiku-4-5",
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            estimated_cost=0.0035,
        )
        for i in range(n)
    ]
    context["usage_port"].set_rows(new_rows)


@when("我用 dry_run_token 執行 recalculate execute")
def execute_with_token(context):
    uc = ExecuteRecalculateUseCase(
        pricing_repo=context["pricing_repo"],
        audit_repo=context["audit_repo"],
        usage_port=context["usage_port"],
        cache=context["cache"],
    )
    try:
        result = run(
            uc.execute(
                ExecuteRecalculateCommand(
                    dry_run_token=context["dry_run"].dry_run_token,
                    reason="補算",
                    actor="admin",
                )
            )
        )
        context["execute_result"] = result
    except Exception as exc:
        context["error"] = exc


@given(parsers.parse("dry-run 回傳 affected_rows={n:d} cost_delta={delta:g}"))
def dry_run_with_delta(context, n, delta):
    dry_run_rows_given(context, n)


@when(
    parsers.parse(
        '我用 dry_run_token 執行 recalculate execute reason="{reason}"'
    )
)
def execute_with_reason(context, reason):
    uc = ExecuteRecalculateUseCase(
        pricing_repo=context["pricing_repo"],
        audit_repo=context["audit_repo"],
        usage_port=context["usage_port"],
        cache=context["cache"],
    )
    result = run(
        uc.execute(
            ExecuteRecalculateCommand(
                dry_run_token=context["dry_run"].dry_run_token,
                reason=reason,
                actor="admin",
            )
        )
    )
    context["execute_result"] = result


def _build_pricing_and_deps_if_missing(context):
    if "pricing_repo" not in context:
        context.setdefault("usage_rows", [])
        context.setdefault("prefix", "anthropic")
        context.setdefault("model_id", "claude-haiku-4-5")
        _build_pricing_and_deps(context, 1.0, 5.0)


# ── Then ──────────────────────────────────────────────────────


@then(parsers.parse("回傳 affected_rows 應為 {n:d}"))
def assert_dry_run_rows(context, n):
    assert context["dry_run"].affected_rows == n


@then(parsers.parse("回傳 cost_before_total 應為 {v:g}"))
def assert_cost_before(context, v):
    assert context["dry_run"].cost_before_total == pytest.approx(v, rel=0.01)


@then("回傳 cost_after_total 應大於 cost_before_total")
def assert_cost_after_greater(context):
    assert (
        context["dry_run"].cost_after_total
        > context["dry_run"].cost_before_total
    )


@then("回傳應含有 dry_run_token")
def assert_token(context):
    assert context["dry_run"].dry_run_token
    assert len(context["dry_run"].dry_run_token) >= 32


@then(parsers.parse('應拋出 PermissionError 訊息包含 "{needle}"'))
def assert_permission_error(context, needle):
    err = context.get("error")
    assert isinstance(err, PermissionError), f"got {err!r}"
    assert needle.lower() in str(err).lower()


@then(parsers.parse('應拋出 RuntimeError 訊息包含 "{needle}"'))
def assert_runtime_error(context, needle):
    err = context.get("error")
    assert isinstance(err, RuntimeError), f"got {err!r}"
    assert needle.lower() in str(err).lower()


@then(parsers.parse('應拋出 ValueError 訊息包含 "{needle}"'))
def assert_value_error(context, needle):
    err = context.get("error")
    assert isinstance(err, ValueError), f"got {err!r}"
    assert needle.lower() in str(err).lower()


@then("token_usage_records 應保持原 estimated_cost 不變")
def assert_no_updates(context):
    assert context["usage_port"].updates == []


@then("pricing_recalc_audit 應新增 1 筆紀錄 executed_by 為 admin id")
def assert_audit_saved(context):
    assert len(context["audit_repo"].saved) == 1
    assert context["audit_repo"].saved[0].executed_by == "admin"


@then(parsers.parse("該區間的 {n:d} 筆 token_usage_records 的 cost_recalc_at 應被設定為當前時間"))
def assert_recalc_at(context, n):
    assert context["usage_port"].recalc_at is not None
    assert len(context["usage_port"].updates) == n


@then(parsers.parse("{n:d} 筆 row 的 estimated_cost 應更新為新價格計算值"))
def assert_cost_updated(context, n):
    # 每筆的 new cost 應符合 1.10/1M * 1000 + 5.50/1M * 500 = 0.0011 + 0.00275 = 0.00385
    expected = 1000 * 1.10 / 1_000_000 + 500 * 5.50 / 1_000_000
    for _, new_cost in context["usage_port"].updates:
        assert new_cost == pytest.approx(expected, rel=1e-6)
