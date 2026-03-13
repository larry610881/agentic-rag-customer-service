"""BDD steps for Bot LLM/Eval field validation."""
import pytest
from fastapi import HTTPException
from pytest_bdd import given, parsers, scenarios, then, when

from src.interfaces.api.bot_router import _validate_llm_fields

scenarios("unit/bot/bot_llm_validation.feature")


@pytest.fixture
def context():
    return {}


@given(parsers.re(
    r'一個建立 Bot 請求帶有 llm_provider "(?P<provider>[^"]*)"'
    r' 和 llm_model "(?P<model>[^"]*)"',
))
def setup_llm_fields(context, provider, model):
    context["llm_provider"] = provider
    context["llm_model"] = model
    context["eval_provider"] = ""
    context["eval_model"] = ""


@given(parsers.re(
    r'一個建立 Bot 請求帶有 eval_provider "(?P<provider>[^"]*)"'
    r' 和 eval_model "(?P<model>[^"]*)"',
))
def setup_eval_fields(context, provider, model):
    context["llm_provider"] = ""
    context["llm_model"] = ""
    context["eval_provider"] = provider
    context["eval_model"] = model


@when("執行 LLM 欄位校驗")
def run_validation(context):
    try:
        _validate_llm_fields(
            context["llm_provider"],
            context["llm_model"],
            context["eval_provider"],
            context["eval_model"],
        )
        context["error"] = None
    except HTTPException as e:
        context["error"] = e


@then("不應拋出異常")
def no_error(context):
    assert context["error"] is None


@then(parsers.parse('應拋出 400 錯誤包含 "{msg}"'))
def check_400_error(context, msg):
    assert context["error"] is not None
    assert context["error"].status_code == 400
    assert msg in context["error"].detail
