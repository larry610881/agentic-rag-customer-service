"""TeamSupervisor 團隊路由 BDD Step Definitions"""

import asyncio

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.agent.team_supervisor import TeamSupervisor
from src.domain.agent.worker import AgentWorker, WorkerContext, WorkerResult
from src.domain.rag.value_objects import TokenUsage

scenarios("unit/agent/team_supervisor_routing.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _MockWorker(AgentWorker):
    """測試用 Worker，可控制 can_handle 結果"""

    def __init__(self, worker_name: str, handles: bool = True) -> None:
        self._name = worker_name
        self._handles = handles
        self.handle_called = False

    @property
    def name(self) -> str:
        return self._name

    async def can_handle(self, context: WorkerContext) -> bool:
        return self._handles

    async def handle(self, context: WorkerContext) -> WorkerResult:
        self.handle_called = True
        return WorkerResult(
            answer=f"{self._name} 已處理",
            usage=TokenUsage.zero("fake"),
        )


@pytest.fixture
def context():
    return {}


@given("團隊包含 WorkerA 和 WorkerB")
def setup_workers(context):
    context["worker_a"] = _MockWorker("worker_a")
    context["worker_b"] = _MockWorker("worker_b")


@given("WorkerA 能處理該訊息")
def worker_a_can_handle(context):
    context["worker_a"]._handles = True


@given("WorkerA 無法處理該訊息")
def worker_a_cannot_handle(context):
    context["worker_a"]._handles = False


@given("WorkerB 能處理該訊息")
def worker_b_can_handle(context):
    context["worker_b"]._handles = True


@given("WorkerB 無法處理該訊息")
def worker_b_cannot_handle(context):
    context["worker_b"]._handles = False


@when("TeamSupervisor 處理訊息 \"我要退貨\"", target_fixture="result")
def handle_refund_message(context):
    supervisor = TeamSupervisor(
        team_name="test_team",
        workers=[context["worker_a"], context["worker_b"]],
    )
    ctx = WorkerContext(
        tenant_id="tenant-001", kb_id="kb-001", user_message="我要退貨"
    )
    return _run(supervisor.handle(ctx))


@when("TeamSupervisor 處理訊息 \"查詢商品\"", target_fixture="result")
def handle_product_message(context):
    supervisor = TeamSupervisor(
        team_name="test_team",
        workers=[context["worker_a"], context["worker_b"]],
    )
    ctx = WorkerContext(
        tenant_id="tenant-001", kb_id="kb-001", user_message="查詢商品"
    )
    return _run(supervisor.handle(ctx))


@when("TeamSupervisor 處理訊息 \"隨機亂打\"", target_fixture="result")
def handle_random_message(context):
    supervisor = TeamSupervisor(
        team_name="test_team",
        workers=[context["worker_a"], context["worker_b"]],
    )
    ctx = WorkerContext(
        tenant_id="tenant-001", kb_id="kb-001", user_message="隨機亂打"
    )
    return _run(supervisor.handle(ctx))


@then("應由 WorkerA 回應")
def verify_worker_a_responded(result, context):
    assert result.answer == "worker_a 已處理"
    assert context["worker_a"].handle_called is True


@then("WorkerB 不應被呼叫")
def verify_worker_b_not_called(context):
    assert context["worker_b"].handle_called is False


@then("應由 WorkerB 回應")
def verify_worker_b_responded(result, context):
    assert result.answer == "worker_b 已處理"
    assert context["worker_b"].handle_called is True


@then("應回傳無法處理的預設訊息")
def verify_default_response(result):
    assert "無法處理" in result.answer
