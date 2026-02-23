"""情緒偵測 BDD Step Definitions"""

import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.infrastructure.langgraph.supervisor_agent_service import (
    SupervisorAgentService,
)
from src.infrastructure.langgraph.workers.fake_main_worker import FakeMainWorker
from src.infrastructure.sentiment.keyword_sentiment_service import (
    KeywordSentimentService,
)

scenarios("unit/agent/sentiment_detection.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given("情緒偵測服務已初始化")
def sentiment_service_initialized(context):
    context["agent"] = SupervisorAgentService(
        workers=[FakeMainWorker()],
        sentiment_service=KeywordSentimentService(),
    )


@when(parsers.parse('用戶發送負面訊息 "{msg}"'))
def send_negative_message(context, msg):
    context["response"] = _run(
        context["agent"].process_message(
            tenant_id="tenant-001",
            kb_id="kb-001",
            user_message=msg,
        )
    )


@when(parsers.parse('用戶發送正常訊息 "{msg}"'))
def send_neutral_message(context, msg):
    context["response"] = _run(
        context["agent"].process_message(
            tenant_id="tenant-001",
            kb_id="kb-001",
            user_message=msg,
        )
    )


@then(parsers.parse('情緒應為 "{sentiment}"'))
def verify_sentiment(context, sentiment):
    assert context["response"].sentiment == sentiment


@then("應標記為需升級")
def verify_escalated(context):
    assert context["response"].escalated is True


@then("不應標記為需升級")
def verify_not_escalated(context):
    assert context["response"].escalated is False
