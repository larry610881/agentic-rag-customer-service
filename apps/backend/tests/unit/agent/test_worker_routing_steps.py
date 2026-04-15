"""BDD steps for Worker routing classification."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.intent_classifier import IntentClassifier
from src.domain.bot.worker_config import WorkerConfig

scenarios("unit/agent/worker_routing.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_worker(name: str, description: str = "") -> WorkerConfig:
    return WorkerConfig(
        bot_id="bot-001",
        name=name,
        description=description or f"{name} 相關問題",
        worker_prompt=f"你是{name}專員",
    )


@pytest.fixture()
def context():
    return {}


# ---------- Given ----------

@given("IntentClassifier 已初始化")
def init_classifier(context):
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock()
    context["mock_llm"] = mock_llm
    context["classifier"] = IntentClassifier(llm_service=mock_llm)


@given(parsers.parse(
    '有 {count:d} 個 Workers 分別為 "{w1}" 和 "{w2}"'
))
def setup_two_workers(context, count, w1, w2):
    context["workers"] = [_make_worker(w1), _make_worker(w2)]


@given(parsers.parse('有 {count:d} 個 Worker 名為 "{name}"'))
def setup_one_worker(context, count, name):
    context["workers"] = [_make_worker(name)]


# ---------- When ----------

@when(parsers.parse('LLM 回傳分類結果 "{result}"'))
def llm_returns(context, result):
    context["mock_llm"].generate.return_value = SimpleNamespace(
        text=result
    )
    context["result"] = _run(
        context["classifier"].classify_workers(
            user_message="測試訊息",
            router_context="",
            workers=context["workers"],
        )
    )


@when("以空的 Workers 清單分類")
def classify_empty(context):
    context["result"] = _run(
        context["classifier"].classify_workers(
            user_message="測試訊息",
            router_context="",
            workers=[],
        )
    )


@when("LLM 呼叫拋出例外")
def llm_raises(context):
    context["mock_llm"].generate.side_effect = RuntimeError(
        "LLM unavailable"
    )
    context["result"] = _run(
        context["classifier"].classify_workers(
            user_message="測試訊息",
            router_context="",
            workers=context["workers"],
        )
    )


# ---------- Then ----------

@then(parsers.parse('應回傳名為 "{name}" 的 WorkerConfig'))
def check_matched_worker(context, name):
    assert context["result"] is not None
    assert context["result"].name == name


@then("應回傳 None")
def check_none(context):
    assert context["result"] is None


@then("LLM 不應被呼叫")
def check_llm_not_called(context):
    context["mock_llm"].generate.assert_not_called()
