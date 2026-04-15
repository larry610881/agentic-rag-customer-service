"""BDD steps for System Prompt 分層組裝 (PromptAssembler)."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.prompt_assembler import assemble

scenarios("unit/agent/prompt_assembler.feature")


@pytest.fixture()
def context():
    return {}


@given(parsers.parse('system_prompt 為 "{prompt}"'))
def set_system_prompt(context, prompt):
    context["system_prompt"] = prompt


@given("system_prompt 為空")
def empty_system_prompt(context):
    context["system_prompt"] = ""


@given("沒有自定義 Bot 提示詞")
def no_custom_prompt(context):
    context["bot_prompt"] = None


@given(parsers.parse('自定義 Bot 提示詞為 "{prompt}"'))
def custom_prompt(context, prompt):
    context["bot_prompt"] = prompt


@when("組裝系統提示詞")
def assemble_prompt_step(context):
    context["result"] = assemble(
        bot_prompt=context.get("bot_prompt"),
        system_prompt=context.get("system_prompt", ""),
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
