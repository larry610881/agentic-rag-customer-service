"""BDD step defs — unit/pricing/pricing_crud.feature"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.pricing.create_pricing_use_case import (
    CreatePricingCommand,
    CreatePricingUseCase,
)
from src.application.pricing.deactivate_pricing_use_case import (
    DeactivatePricingCommand,
    DeactivatePricingUseCase,
)
from src.application.pricing.list_pricing_use_case import ListPricingUseCase
from src.domain.pricing.entity import ModelPricing
from src.domain.pricing.value_objects import PriceRate, PricingCategory
from tests.unit.pricing.conftest import FakeModelPricingRepo, run

scenarios("unit/pricing/pricing_crud.feature")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@given(parsers.parse('尚未有任何 "{provider}" "{model_id}" 的 pricing 版本'))
def empty_repo(context, provider, model_id):
    context["repo"] = FakeModelPricingRepo()
    context["provider"] = provider
    context["model_id"] = model_id


@given(
    parsers.parse(
        '已有一筆 "{provider}" "{model_id}" pricing 生效中 input={inp:g} output={out:g}'
    )
)
def seeded_active(context, provider, model_id, inp, out):
    context.setdefault("repo", FakeModelPricingRepo())
    p = ModelPricing(
        provider=provider,
        model_id=model_id,
        display_name=model_id,
        rate=PriceRate(input_price=inp, output_price=out),
        effective_from=_now() - timedelta(hours=1),
        created_by="seed",
        note="seed",
    )
    run(context["repo"].save(p))
    context["existing"] = p
    context["provider"] = provider
    context["model_id"] = model_id


@given(
    parsers.parse(
        '已有一筆 "{provider}" "{model_id}" pricing 生效中 input={inp:g}'
    )
)
def seeded_active_only_input(context, provider, model_id, inp):
    seeded_active(context, provider, model_id, inp, 5.0)


@given(
    parsers.parse(
        '已有一筆 "{provider}" "{model_id}" pricing 排程 effective_from 為 {hrs:d} 小時後 input={inp:g}'
    )
)
def seeded_scheduled(context, provider, model_id, hrs, inp):
    context.setdefault("repo", FakeModelPricingRepo())
    p = ModelPricing(
        provider=provider,
        model_id=model_id,
        display_name=model_id,
        rate=PriceRate(input_price=inp, output_price=5.0),
        effective_from=_now() + timedelta(hours=hrs),
        created_by="seed",
        note="scheduled",
    )
    run(context["repo"].save(p))


@given(parsers.parse('已有一筆 "{provider}" "{model_id}" pricing 生效中'))
def seeded_active_default(context, provider, model_id):
    seeded_active(context, provider, model_id, 1.0, 5.0)


@given(
    parsers.parse(
        '已有一筆 "{provider}" "{model_id}" pricing 生效中 id 為 "{pid}"'
    )
)
def seeded_active_with_id(context, provider, model_id, pid):
    context.setdefault("repo", FakeModelPricingRepo())
    p = ModelPricing(
        id=pid,
        provider=provider,
        model_id=model_id,
        display_name=model_id,
        rate=PriceRate(1.0, 5.0),
        effective_from=_now() - timedelta(hours=1),
        created_by="seed",
        note="seed",
    )
    run(context["repo"].save(p))
    context["pid"] = pid


@when(
    parsers.parse(
        '我建立一筆 pricing "{provider}" "{model_id}" input={inp:g} output={out:g} effective_from 為未來時間'
    )
)
def create_future(context, provider, model_id, inp, out):
    uc = CreatePricingUseCase(repo=context["repo"])
    try:
        result = run(
            uc.execute(
                CreatePricingCommand(
                    provider=provider,
                    model_id=model_id,
                    display_name=model_id,
                    input_price=inp,
                    output_price=out,
                    cache_read_price=0.0,
                    cache_creation_price=0.0,
                    effective_from=_now() + timedelta(minutes=1),
                    note="test",
                    created_by="admin@test",
                )
            )
        )
        context["result"] = result
    except Exception as exc:
        context["error"] = exc


@when(
    parsers.parse(
        '我建立新版本 "{provider}" "{model_id}" input={inp:g} output={out:g} effective_from 為 1 分鐘後'
    )
)
def create_new_version(context, provider, model_id, inp, out):
    eff = _now() + timedelta(minutes=1)
    context["new_effective_from"] = eff
    uc = CreatePricingUseCase(repo=context["repo"])
    result = run(
        uc.execute(
            CreatePricingCommand(
                provider=provider,
                model_id=model_id,
                display_name=model_id,
                input_price=inp,
                output_price=out,
                cache_read_price=0.0,
                cache_creation_price=0.0,
                effective_from=eff,
                note="price bump",
                created_by="admin@test",
            )
        )
    )
    context["new_version"] = result


@when(
    parsers.parse(
        '我建立一筆 pricing "{provider}" "{model_id}" input={inp:g} output={out:g} effective_from 為 1 分鐘前'
    )
)
def create_past(context, provider, model_id, inp, out):
    uc = CreatePricingUseCase(repo=context["repo"])
    try:
        run(
            uc.execute(
                CreatePricingCommand(
                    provider=provider,
                    model_id=model_id,
                    display_name=model_id,
                    input_price=inp,
                    output_price=out,
                    cache_read_price=0.0,
                    cache_creation_price=0.0,
                    effective_from=_now() - timedelta(minutes=1),
                    note="test",
                    created_by="admin@test",
                )
            )
        )
    except Exception as exc:
        context["error"] = exc


@when(
    parsers.parse(
        '我建立一筆 pricing "{provider}" "{model_id}" input={inp:g} output={out:g} effective_from 為未來時間 但 note 為空字串'
    )
)
def create_empty_note(context, provider, model_id, inp, out):
    context.setdefault("repo", FakeModelPricingRepo())
    uc = CreatePricingUseCase(repo=context["repo"])
    try:
        run(
            uc.execute(
                CreatePricingCommand(
                    provider=provider,
                    model_id=model_id,
                    display_name=model_id,
                    input_price=inp,
                    output_price=out,
                    cache_read_price=0.0,
                    cache_creation_price=0.0,
                    effective_from=_now() + timedelta(minutes=1),
                    note="",
                    created_by="admin@test",
                )
            )
        )
    except Exception as exc:
        context["error"] = exc


@when("我停用該版本")
def deactivate(context):
    uc = DeactivatePricingUseCase(repo=context["repo"])
    # 找第一個 seeded active
    existing = context.get("existing") or context["repo"]._items[0]
    run(uc.execute(DeactivatePricingCommand(pricing_id=existing.id, actor="admin")))
    context["deactivated"] = existing


@when("我列出所有 pricing 版本")
def list_all(context):
    uc = ListPricingUseCase(repo=context["repo"])
    context["list_result"] = run(uc.execute())


# ── Then ──────────────────────────────────────────────────────


@then("新版本應寫入 repository")
def assert_saved(context):
    assert len(context["repo"]._items) >= 1


@then("新版本的 effective_to 應為 None")
def assert_effective_to_none(context):
    assert context["result"].effective_to is None


@then("舊版本的 effective_to 應等於新版本的 effective_from")
def assert_effective_to_pinned(context):
    existing = context["existing"]
    assert existing.effective_to == context["new_effective_from"]


@then(parsers.parse("最新生效版本查 at=now+2min 應為 input={inp:g}"))
def assert_latest_active(context, inp):
    repo = context["repo"]
    at = _now() + timedelta(minutes=2)
    active = run(
        repo.find_active_version(
            provider=context["provider"],
            model_id=context["model_id"],
            at=at,
        )
    )
    assert active is not None
    assert active.rate.input_price == pytest.approx(inp)


@then(parsers.parse('應拋出 ValueError 訊息包含 "{needle}"'))
def assert_value_error(context, needle):
    err = context.get("error")
    assert isinstance(err, ValueError), f"expected ValueError, got {err!r}"
    assert needle in str(err), f"expected {needle!r} in {str(err)!r}"


@then("該版本的 effective_to 應設為當前時間")
def assert_deactivated(context):
    d = context["deactivated"]
    assert d.effective_to is not None


@then(
    parsers.parse(
        '查詢 at=now+1min 時應查不到 "{provider}" "{model_id}" 的生效版本'
    )
)
def assert_query_miss(context, provider, model_id):
    repo = context["repo"]
    at = _now() + timedelta(minutes=1)
    result = run(repo.find_active_version(provider=provider, model_id=model_id, at=at))
    assert result is None


@then("回傳應包含目前生效版本")
def assert_contains_active(context):
    results = context["list_result"]
    now = _now()
    assert any(
        p.effective_from <= now and (p.effective_to is None or p.effective_to > now)
        for p in results
    )


@then("回傳應包含排程未生效版本")
def assert_contains_scheduled(context):
    results = context["list_result"]
    now = _now()
    assert any(p.effective_from > now for p in results)
