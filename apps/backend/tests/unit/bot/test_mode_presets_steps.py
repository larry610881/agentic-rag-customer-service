"""情境預設與可組合設定 BDD Steps — Issue #92

紅線：**mode 只是標籤，不驅動行為**；後台顯示什麼就是實際行為什麼。
反例來源：kb 模式在管線硬關 rerank，後台開關可打開、存檔成功、實際無效且無提示。
"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.mode_presets import preset_values, unmet_prerequisites
from src.domain.bot.value_objects import BotId

scenarios("unit/bot/bot_mode_presets.feature")


def _bot(**kw) -> Bot:
    base = dict(
        id=BotId(value="b1"),
        tenant_id="t1",
        name="b",
        knowledge_base_ids=["kb-1"],
        llm_params=BotLLMParams(),
    )
    base.update(kw)
    return Bot(**base)


def _apply(bot: Bot, mode: str) -> Bot:
    for k, v in preset_values(mode).items():
        setattr(bot, k, v)
    bot.mode = mode
    return bot


@pytest.fixture
def context():
    return {}


# --- When ---


@when(parsers.parse('套用情境預設 "{mode}"'))
def _when_apply_preset(context, mode):
    context["bot"] = _apply(_bot(), mode)


@given(parsers.parse('已套用情境預設 "{mode}"'))
def _given_applied(context, mode):
    context["bot"] = _apply(_bot(), mode)


@given(parsers.parse('一個 bot 其 mode 為 "{mode}" 但 rerank_enabled 為 true'))
def _given_mode_label_only(context, mode):
    bot = _bot()
    bot.mode = mode
    bot.rerank_enabled = True
    context["bot"] = bot


@given(
    parsers.parse(
        "一個 bot 其 direct_retrieval 為 true 且 escalate_on_miss 為 {flag}"
    )
)
def _given_miss_behaviour(context, flag):
    bot = _bot(enabled_tools=["rag_query"])
    bot.direct_retrieval = True
    bot.escalate_on_miss = flag.strip().lower() == "true"
    context["bot"] = bot


@given("一個 bot 已綁定知識庫")
def _given_kb_bound(context):
    context["bot"] = _bot(knowledge_base_ids=["kb-1"])


@when(parsers.parse('我把 "{field}" 改為 true'))
def _when_flip_on(context, field):
    setattr(context["bot"], field, True)


@when("解析該 bot 的檢索計畫")
def _when_resolve_plan(context):
    pass  # 計畫解析在 Then 以 allow_rerank 的判準檢查


@when("檢索未達門檻")
def _when_miss(context):
    context["missed"] = True


@when(parsers.parse('我送出設定 "{field}" 為 {value} 但前置條件未滿足'))
def _when_submit_unmet(context, field, value):
    kw = {"knowledge_base_ids": [], "enabled_tools": []}
    bot = _bot(**kw)
    setattr(bot, field, value.strip().lower() == "true")
    context["bot"] = bot
    context["unmet"] = unmet_prerequisites(bot)


@when(parsers.parse('我送出設定 "{field}" 為 true 但前置條件已滿足'))
def _when_submit_met(context, field):
    bot = context.get("bot") or _bot()
    setattr(bot, field, True)
    context["bot"] = bot
    context["unmet"] = unmet_prerequisites(bot)


# --- Then ---


@then(parsers.parse('設定 "{field}" 應為 {expected}'))
def _then_field_is(context, field, expected):
    want = expected.strip().lower() == "true"
    assert getattr(context["bot"], field) is want, (
        f"{field} 應為 {want}，實際 {getattr(context['bot'], field)!r}"
    )


@then("設定的可用工具應為空")
def _then_tools_empty(context):
    assert context["bot"].enabled_tools == []


@then("解析後的檢索計畫應允許 rerank")
def _then_plan_allows_rerank(context):
    from src.application.agent.send_message_use_case import resolve_allow_rerank

    assert resolve_allow_rerank(context["bot"]) is True, (
        "rerank_enabled 開著卻不允許 rerank —— mode 又在覆蓋設定了"
    )


@then("應回未命中話術且不升級推理")
def _then_miss_reply(context):
    assert context["bot"].escalate_on_miss is False


@then("應升級推理")
def _then_escalate(context):
    assert context["bot"].escalate_on_miss is True


@then(parsers.parse('應被拒絕並說明缺少的前置條件 "{prereq}"'))
def _then_rejected(context, prereq):
    unmet = context["unmet"]
    assert unmet, "無效組合竟然通過了後端驗證"
    fields = {u[1] for u in unmet}
    assert prereq in fields, f"缺少的前置條件應含 {prereq}，實際 {fields}"


@then("設定應被接受")
def _then_accepted(context):
    assert context["unmet"] == [], f"不該被擋：{context['unmet']}"
