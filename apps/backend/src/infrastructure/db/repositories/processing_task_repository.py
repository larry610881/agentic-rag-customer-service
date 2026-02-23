from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.knowledge.entity import ProcessingTask
from src.domain.knowledge.repository import ProcessingTaskRepository
from src.domain.knowledge.value_objects import ProcessingTaskId
from src.infrastructure.db.models.processing_task_model import (
    ProcessingTaskModel,
)


class SQLAlchemyProcessingTaskRepository(ProcessingTaskRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: ProcessingTaskModel) -> ProcessingTask:
        return ProcessingTask(
            id=ProcessingTaskId(value=model.id),
            document_id=model.document_id,
            tenant_id=model.tenant_id,
            status=model.status,
            progress=model.progress,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, task: ProcessingTask) -> None:
        model = ProcessingTaskModel(
            id=task.id.value,
            document_id=task.document_id,
            tenant_id=task.tenant_id,
            status=task.status,
            progress=task.progress,
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        self._session.add(model)
        await self._session.commit()

    async def find_by_id(
        self, task_id: str
    ) -> ProcessingTask | None:
        stmt = select(ProcessingTaskModel).where(
            ProcessingTaskModel.id == task_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update_status(
        self,
        task_id: str,
        status: str,
        progress: int | None = None,
        error_message: str | None = None,
    ) -> None:
        values: dict = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }
        if progress is not None:
            values["progress"] = progress
        if error_message is not None:
            values["error_message"] = error_message
        stmt = (
            update(ProcessingTaskModel)
            .where(ProcessingTaskModel.id == task_id)
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.commit()
