"""TeamSupervisor — 團隊級 Supervisor，本身也是 AgentWorker"""

from src.domain.agent.worker import AgentWorker, WorkerContext, WorkerResult


class TeamSupervisor(AgentWorker):
    """團隊 Supervisor：持有一組 Worker，依序 dispatch。

    TeamSupervisor 本身就是 AgentWorker，可被上層 MetaSupervisor dispatch。
    遵循 Open-Closed Principle — AgentWorker ABC 不需修改。
    """

    def __init__(self, team_name: str, workers: list[AgentWorker]) -> None:
        self._team_name = team_name
        self._workers = workers

    @property
    def name(self) -> str:
        return self._team_name

    async def can_handle(self, context: WorkerContext) -> bool:
        return any(
            await worker.can_handle(context) for worker in self._workers
        )

    async def handle(self, context: WorkerContext) -> WorkerResult:
        for worker in self._workers:
            if await worker.can_handle(context):
                return await worker.handle(context)
        return WorkerResult(answer="抱歉，我無法處理此請求。")
