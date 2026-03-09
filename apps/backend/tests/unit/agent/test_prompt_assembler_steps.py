"""BDD steps for System Prompt 分層組裝 (PromptAssembler)."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.prompt_assembler import assemble

scenarios("unit/agent/prompt_assembler.feature")


@pytest.fixture()
def context():
    return {}


@given(parsers.parse('base_prompt 為 "{prompt}"'))
def set_base_prompt(context, prompt):
    context["base_prompt"] = prompt


@given(parsers.parse('mode_prompt 為 "{prompt}"'))
def set_mode_prompt(context, prompt):
    context["mode_prompt"] = prompt


@given("base_prompt 為空")
def empty_base_prompt(context):
    context["base_prompt"] = ""


@given("mode_prompt 為空")
def empty_mode_prompt(context):
    context["mode_prompt"] = ""


@given("沒有自定義 Bot 提示詞")
def no_custom_prompt(context):
    context["bot_prompt"] = None


@given(parsers.parse('自定義 Bot 提示詞為 "{prompt}"'))
def custom_prompt(context, prompt):
    context["bot_prompt"] = prompt


@when("組裝系統提示詞")
def assemble_prompt(context):
    context["result"] = assemble(
        bot_prompt=context.get("bot_prompt"),
        base_prompt=context.get("base_prompt", ""),
        mode_prompt=context.get("mode_prompt", ""),
    )


@then(parsers.parse('結果應包含 "{text}"'))
def check_contains_text(context, text):
    assert text in context["result"]


@then(parsers.parse('結果不應包含 "{text}"'))
def check_not_contains_text(context, text):
    assert text not in context["result"]


@then("結果應為空字串")
def check_empty_result(context):
    assert context["result"] == ""


@then(parsers.parse('結果應等於 "{text}"'))
def check_equals_text(context, text):
    assert context["result"] == text
