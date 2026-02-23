"""MetaSupervisor 角色路由 BDD Step Definitions"""

import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.agent.team_supervisor import TeamSupervisor
from src.domain.agent.worker import AgentWorker, WorkerContext, WorkerResult
from src.domain.rag.value_objects import TokenUsage
from src.infrastructure.langgraph.meta_supervisor_service import (
    MetaSupervisorService,
)
from src.infrastructure.sentiment.keyword_sentiment_service import (
    KeywordSentimentService,
)

scenarios("unit/agent/meta_supervisor_routing.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _TeamStubWorker(AgentWorker):
    """測試用 Worker，記錄被哪個團隊呼叫"""

    def __init__(self, team_label: str) -> None:
        self._team_label = team_label

    @property
    def name(self) -> str:
        return f"stub_{self._team_label}"

    async def can_handle(self, context: WorkerContext) -> bool:
        return True

    async def handle(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(
            answer=f"由 {self._team_label} 團隊處理",
            usage=TokenUsage.zero("fake"),
            metadata={"handled_by_team": self._team_label},
        )


@pytest.fixture
def context():
    return {}


@given("MetaSupervisor 已註冊 customer 和 marketing 團隊")
def setup_meta_supervisor(context):
    context["customer_team"] = TeamSupervisor(
        team_name="customer",
        workers=[_TeamStubWorker("customer")],
    )
    context["marketing_team"] = TeamSupervisor(
        team_name="marketing",
        workers=[_TeamStubWorker("marketing")],
    )
    context["teams"] = {
        "customer": context["customer_team"],
        "marketing": context["marketing_team"],
    }


@given(parsers.parse('使用者角色為 "{role}"'))
def set_user_role(context, role):
    context["user_role"] = role


@given("情緒服務已啟用")
def enable_sentiment(context):
    context["sentiment_service"] = KeywordSentimentService()


@when(parsers.parse('MetaSupervisor 處理訊息 "{msg}"'))
def process_message(context, msg):
    sentiment_svc = context.get("sentiment_service")
    meta = MetaSupervisorService(
        teams=context["teams"],
        sentiment_service=sentiment_svc,
    )
    context["response"] = _run(
        meta.process_message(
            tenant_id="tenant-001",
            kb_id="kb-001",
            user_message=msg,
            user_role=context["user_role"],
        )
    )


@when(parsers.parse('MetaSupervisor 處理包含負面情緒的訊息 "{msg}"'))
def process_negative_message(context, msg):
    meta = MetaSupervisorService(
        teams=context["teams"],
        sentiment_service=context["sentiment_service"],
    )
    context["response"] = _run(
        meta.process_message(
            tenant_id="tenant-001",
            kb_id="kb-001",
            user_message=msg,
            user_role=context["user_role"],
        )
    )


@then("應由 customer 團隊處理")
def verify_customer_team(context):
    assert "customer" in context["response"].answer


@then("應由 marketing 團隊處理")
def verify_marketing_team(context):
    assert "marketing" in context["response"].answer


@then("回應中應包含 conversation_id")
def verify_conversation_id(context):
    assert context["response"].conversation_id != ""


@then(parsers.parse('回應應包含 sentiment 為 "{sentiment}"'))
def verify_sentiment(context, sentiment):
    assert context["response"].sentiment == sentiment


@then("回應應標記為需要升級")
def verify_escalated(context):
    assert context["response"].escalated is True
