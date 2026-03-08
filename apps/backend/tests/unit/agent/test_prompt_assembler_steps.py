"""BDD steps for System Prompt 分層組裝 (PromptAssembler)."""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.prompt_assembler import (
    BASE_PROMPT,
    REACT_MODE_PROMPT,
    ROUTER_MODE_PROMPT,
    assemble,
)

scenarios("unit/agent/prompt_assembler.feature")


@pytest.fixture()
def context():
    return {}


@given("沒有自定義 Bot 提示詞")
def no_custom_prompt(context):
    context["bot_prompt"] = None


@given(parsers.parse('自定義 Bot 提示詞為 "{prompt}"'))
def custom_prompt(context, prompt):
    context["bot_prompt"] = prompt


@when(parsers.parse('以 "{mode}" 模式組裝系統提示詞'))
def assemble_prompt(context, mode):
    context["result"] = assemble(context["bot_prompt"], mode)


@then("結果應包含基礎品牌聲音")
def check_base_prompt(context):
    assert BASE_PROMPT in context["result"]


@then("結果應包含 Router 模式指令")
def check_router_prompt(context):
    assert ROUTER_MODE_PROMPT in context["result"]


@then("結果應包含 ReAct 推理策略")
def check_react_prompt(context):
    assert REACT_MODE_PROMPT in context["result"]


@then("結果不應包含 ReAct 推理策略")
def check_no_react_prompt(context):
    assert REACT_MODE_PROMPT not in context["result"]


@then("結果不應包含 Router 模式指令")
def check_no_router_prompt(context):
    assert ROUTER_MODE_PROMPT not in context["result"]


@then(parsers.parse('結果應包含 "{text}"'))
def check_contains_text(context, text):
    assert text in context["result"]


@then(parsers.parse('結果不應包含 "{text}"'))
def check_not_contains_text(context, text):
    assert text not in context["result"]
