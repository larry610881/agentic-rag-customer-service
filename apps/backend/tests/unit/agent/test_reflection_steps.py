"""Agent 反思 BDD Step Definitions"""

import asyncio

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.agent.worker import AgentWorker, WorkerContext, WorkerResult
from src.domain.rag.value_objects import TokenUsage
from src.infrastructure.langgraph.supervisor_agent_service import (
    SupervisorAgentService,
)

scenarios("unit/agent/agent_reflection.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _StubWorker(AgentWorker):
    """測試用 Worker，可控制回答長度"""

    def __init__(self, answer: str) -> None:
        self._answer = answer

    @property
    def name(self) -> str:
        return "stub"

    async def can_handle(self, context: WorkerContext) -> bool:
        return True

    async def handle(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(
            answer=self._answer,
            usage=TokenUsage.zero("fake"),
        )


@pytest.fixture
def context():
    return {}


@given("反思機制已啟用的 Agent")
def reflection_agent(context):
    context["agent_factory"] = lambda answer: SupervisorAgentService(
        workers=[_StubWorker(answer)],
    )


@when("Agent 產生足夠長度的回答")
def agent_long_answer(context):
    agent = context["agent_factory"]("這是一個足夠長度的回答，包含完整的資訊。")
    context["response"] = _run(
        agent.process_message(
            tenant_id="tenant-001",
            kb_id="kb-001",
            user_message="問題",
        )
    )
    context["original_answer"] = "這是一個足夠長度的回答，包含完整的資訊。"


@when("Agent 產生過短的回答")
def agent_short_answer(context):
    agent = context["agent_factory"]("好的")
    context["response"] = _run(
        agent.process_message(
            tenant_id="tenant-001",
            kb_id="kb-001",
            user_message="問題",
        )
    )


@then("回答不應被修改")
def verify_answer_unchanged(context):
    assert context["response"].answer == context["original_answer"]


@then("回答應被補充延伸")
def verify_answer_extended(context):
    assert len(context["response"].answer) > len("好的")
    assert "如需更多協助" in context["response"].answer
