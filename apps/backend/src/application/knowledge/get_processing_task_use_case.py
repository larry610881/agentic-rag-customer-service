from src.domain.knowledge.entity import ProcessingTask
from src.domain.knowledge.repository import ProcessingTaskRepository
from src.domain.shared.exceptions import EntityNotFoundError


class GetProcessingTaskUseCase:
    def __init__(
        self,
        processing_task_repository: ProcessingTaskRepository,
    ) -> None:
        self._task_repo = processing_task_repository

    async def execute(self, task_id: str) -> ProcessingTask:
        task = await self._task_repo.find_by_id(task_id)
        if task is None:
            raise EntityNotFoundError("ProcessingTask", task_id)
        return task
