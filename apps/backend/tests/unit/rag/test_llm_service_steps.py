"""LLM 服務 BDD Step Definitions"""

import asyncio

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.llm.fake_llm_service import FakeLLMService

scenarios("unit/rag/llm_service.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _collect_stream(gen):
    return [chunk async for chunk in gen]


@pytest.fixture
def context():
    return {}


@pytest.fixture
def fake_llm():
    return FakeLLMService()


@given('一段 context 內容 "退貨政策：30天內可退貨"')
def setup_context(context):
    context["context"] = "退貨政策：30天內可退貨"


@given("空的 context 內容")
def setup_empty_context(context):
    context["context"] = ""


@when("使用 FakeLLMService 生成回答")
def do_generate(context, fake_llm):
    result = _run(
        fake_llm.generate(
            system_prompt="你是客服助手",
            user_message="退貨政策是什麼？",
            context=context["context"],
        )
    )
    context["answer"] = result.text


@when("使用 FakeLLMService streaming 生成回答")
def do_generate_stream(context, fake_llm):
    stream = fake_llm.generate_stream(
        system_prompt="你是客服助手",
        user_message="退貨政策是什麼？",
        context=context["context"],
    )
    context["chunks"] = _run(_collect_stream(stream))


@then('回答應包含 "根據知識庫"')
def verify_has_context(context):
    assert "根據知識庫" in context["answer"]


@then("應收到多個 token chunks")
def verify_multiple_chunks(context):
    assert len(context["chunks"]) > 1


@then('所有 chunks 組合後應包含 "根據知識庫"')
def verify_combined_chunks(context):
    combined = "".join(context["chunks"])
    assert "根據知識庫" in combined


@then('回答應包含 "沒有找到相關資訊"')
def verify_no_knowledge(context):
    assert "沒有找到相關資訊" in context["answer"]
