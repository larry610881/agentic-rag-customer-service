"""Regression: TeamSupervisor.can_handle 曾用 any(await ... for ...)。

生成式內含 await 會變成 async generator，any() 對它拋 TypeError，
導致巢狀 TeamSupervisor 被上層 dispatch 詢問 can_handle 時直接崩潰。
"""

import asyncio

from src.domain.agent.team_supervisor import TeamSupervisor
from src.domain.agent.worker import AgentWorker, WorkerContext, WorkerResult


class _Worker(AgentWorker):
    def __init__(self, handles: bool) -> None:
        self._handles = handles

    @property
    def name(self) -> str:
        return "w"

    async def can_handle(self, context: WorkerContext) -> bool:
        return self._handles

    async def handle(self, context: WorkerContext) -> WorkerResult:
        return WorkerResult(answer="ok")


def _ctx() -> WorkerContext:
    return WorkerContext(tenant_id="t", kb_id="kb", user_message="hi")


def test_can_handle_true_when_any_worker_handles() -> None:
    team = TeamSupervisor("team", [_Worker(False), _Worker(True)])
    assert asyncio.run(team.can_handle(_ctx())) is True


def test_can_handle_false_when_no_worker_handles() -> None:
    team = TeamSupervisor("team", [_Worker(False), _Worker(False)])
    assert asyncio.run(team.can_handle(_ctx())) is False


def test_can_handle_false_for_empty_team() -> None:
    team = TeamSupervisor("team", [])
    assert asyncio.run(team.can_handle(_ctx())) is False
