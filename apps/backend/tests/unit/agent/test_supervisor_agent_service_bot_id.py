"""Regression: SupervisorAgentService 未接受 AgentService 介面的 bot_id 參數。

GuardedAgentService 等上游一律以 bot_id=... 呼叫 inner service；
SupervisorAgentService 若被當成 AgentService 注入，會直接 TypeError。
"""

import asyncio

from src.domain.agent.worker import AgentWorker, WorkerContext, WorkerResult
from src.infrastructure.langgraph.supervisor_agent_service import (
    SupervisorAgentService,
)


class _Worker(AgentWorker):
    @property
    def name(self) -> str:
        return "w"

    async def can_handle(self, context: WorkerContext) -> bool:
        return True

    async def handle(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(answer="ok")


def test_process_message_accepts_bot_id() -> None:
    svc = SupervisorAgentService(workers=[_Worker()])
    resp = asyncio.run(svc.process_message("t", "kb", "hi", bot_id="bot-1"))
    assert resp.answer == "ok"


def test_process_message_stream_accepts_bot_id() -> None:
    svc = SupervisorAgentService(workers=[_Worker()])

    async def _collect() -> list[dict]:
        return [
            e
            async for e in svc.process_message_stream(
                "t", "kb", "hi", bot_id="bot-1"
            )
        ]

    events = asyncio.run(_collect())
    assert events[0] == {"type": "token", "content": "ok"}
