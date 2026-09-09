"""Prompt 分層 BDD Steps — Issue #91

驗證的紅線：**平台防護層（system 層）永遠存在，任何租戶設定或 worker 覆寫都取代不了。**
反例來源：2026-09-09 實測，worker 覆寫與 LINE 通路都把整串 system_prompt 換掉，
平台層一起消失；根因是設定太早把兩層 assemble 成單一字串，之後分不出哪段是防護層。
"""

from dataclasses import dataclass

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.prompt_assembler import assemble, resolve_effective_prompt

scenarios("unit/agent/prompt_layering.feature")

# 通路後綴：真正的內容由各通路常數提供，這裡只驗「後綴不影響前兩層」
_CHANNEL_SUFFIX = {"web": "", "widget": "", "line": "LINE 通路規範"}


@dataclass
class _Worker:
    name: str
    worker_prompt: str


@pytest.fixture
def context():
    return {"system_prompt": "", "bot_prompt": "", "channel_suffix": ""}


# --- Given ---


@given(parsers.parse('平台防護層為 "{text}"'))
def _given_platform(context, text):
    context["system_prompt"] = text


@given(parsers.parse('bot 層為 "{text}"'))
def _given_bot_layer(context, text):
    context["bot_prompt"] = text


@given('bot 層為 ""')
def _given_bot_layer_empty(context):
    context["bot_prompt"] = ""


@given('平台防護層為 ""')
def _given_platform_empty(context):
    context["system_prompt"] = ""


@given(parsers.parse('通路後綴為 "{text}"'))
def _given_suffix(context, text):
    context["channel_suffix"] = text


@given(parsers.parse('一個 bot 其 bot_prompt 為 "{text}"'))
def _given_bot(context, text):
    context["bot_prompt"] = text


@given(parsers.parse('一個 bot 其 base_prompt 為 "{text}"'))
def _given_bot_base(context, text):
    context["base_prompt"] = text


@given(parsers.parse('一個 worker "{name}" 其 worker_prompt 為 "{text}"'))
def _given_worker(context, name, text):
    context["worker"] = _Worker(name=name, worker_prompt=text)


# --- When ---


@when("組裝 effective prompt")
def _when_assemble(context):
    context["effective"] = assemble(
        system_prompt=context["system_prompt"],
        bot_prompt=context["bot_prompt"],
        channel_suffix=context["channel_suffix"],
    )


@when("解析該 bot 的對話設定")
def _when_resolve_cfg(context):
    from src.application.agent.prompt_assembler import resolve_bot_layer

    # 分層解析後兩層必須分開存放，不得提前組裝成單一字串
    context["cfg"] = {
        "system_prompt": context["system_prompt"],
        "bot_prompt": resolve_bot_layer(
            base_prompt=context.get("base_prompt", ""),
            bot_prompt=context["bot_prompt"],
        ),
    }


@when(parsers.parse('worker "{name}" 命中並覆寫設定'))
def _when_worker_override(context, name):
    from src.application.agent.prompt_assembler import apply_worker_override

    context["cfg"] = apply_worker_override(
        {
            "system_prompt": context["system_prompt"],
            "bot_prompt": context["bot_prompt"],
        },
        worker_prompt=context["worker"].worker_prompt,
    )
    context["effective"] = resolve_effective_prompt(context["cfg"])


@when(parsers.parse('以通路 "{channel}" 組裝 effective prompt'))
def _when_assemble_for_channel(context, channel):
    context.setdefault("by_channel", {})
    prompt = resolve_effective_prompt(
        {
            "system_prompt": context["system_prompt"],
            "bot_prompt": context["bot_prompt"],
        },
        channel_suffix=_CHANNEL_SUFFIX[channel],
    )
    context["by_channel"][channel] = prompt
    context["effective"] = prompt


# --- Then ---


@then(
    parsers.parse(
        'effective prompt 應依序包含 "{first}" 然後 "{second}" 然後 "{third}"'
    )
)
def _then_ordered(context, first, second, third):
    text = context["effective"]
    i, j, k = text.find(first), text.find(second), text.find(third)
    assert -1 < i < j < k, f"順序錯誤: {i}, {j}, {k} in {text!r}"


@then(parsers.parse('effective prompt 應包含 "{text}"'))
def _then_contains(context, text):
    assert text in context["effective"], f"{text!r} 不在 {context['effective']!r}"


@then(parsers.parse('effective prompt 不應包含 "{text}"'))
def _then_not_contains(context, text):
    assert text not in context["effective"]


@then(parsers.parse('組裝後的 effective prompt 應包含 "{text}"'))
def _then_effective_contains(context, text):
    assert text in context["effective"], f"{text!r} 不在 {context['effective']!r}"


@then(parsers.parse('組裝後的 effective prompt 不應包含 "{text}"'))
def _then_effective_not_contains(context, text):
    assert text not in context["effective"]


@then(parsers.parse('設定的 system 層應為 "{text}"'))
def _then_cfg_system(context, text):
    assert context["cfg"]["system_prompt"] == text


@then(parsers.parse('設定的 bot 層應為 "{text}"'))
def _then_cfg_bot(context, text):
    assert context["cfg"]["bot_prompt"] == text


@then(parsers.parse('設定的 bot 層應包含 "{text}"'))
def _then_cfg_bot_contains(context, text):
    assert text in context["cfg"]["bot_prompt"], (
        f"{text!r} 不在 bot 層 {context['cfg']['bot_prompt']!r}"
    )


@then(
    parsers.parse(
        'effective prompt 的平台層內容應與通路 "{other}" 的平台層內容相同'
    )
)
def _then_platform_layer_identical(context, other):
    baseline = resolve_effective_prompt(
        {
            "system_prompt": context["system_prompt"],
            "bot_prompt": context["bot_prompt"],
        },
        channel_suffix=_CHANNEL_SUFFIX[other],
    )
    # 系統層是最前段：防護條款永遠打頭，平台設定緊接其後，兩通路完全一致
    from src.domain.platform.prompt_defaults import SECURITY_CLAUSE

    head = f"{SECURITY_CLAUSE}\n\n{context['system_prompt']}"
    assert baseline.startswith(head)
    assert context["effective"].startswith(head)


@then("effective prompt 應包含防護條款")
def _then_has_security_clause(context):
    from src.domain.platform.prompt_defaults import SECURITY_CLAUSE

    assert SECURITY_CLAUSE in context["effective"], (
        "防護條款缺席——這是 Issue #91 的核心不變式"
    )


@then("effective prompt 應以防護條款開頭")
def _then_starts_with_security_clause(context):
    from src.domain.platform.prompt_defaults import SECURITY_CLAUSE

    assert context["effective"].startswith(SECURITY_CLAUSE)
