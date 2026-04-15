"""WorkerConfig Repository 實作"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.bot.worker_config import WorkerConfig
from src.domain.bot.worker_repository import WorkerConfigRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.bot_worker_model import BotWorkerModel


class SQLAlchemyWorkerConfigRepository(WorkerConfigRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: BotWorkerModel) -> WorkerConfig:
        return WorkerConfig(
            id=model.id,
            bot_id=model.bot_id,
            name=model.name,
            description=model.description or "",
            worker_prompt=model.worker_prompt or "",
            llm_provider=model.llm_provider,
            llm_model=model.llm_model,
            temperature=model.temperature,
            max_tokens=model.max_tokens,
            max_tool_calls=model.max_tool_calls,
            enabled_mcp_ids=list(model.enabled_mcp_ids or []),
            knowledge_base_ids=list(model.knowledge_base_ids or []),
            sort_order=model.sort_order,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, worker: WorkerConfig) -> None:
        async with atomic(self._session):
            existing = await self._session.get(
                BotWorkerModel, worker.id
            )
            now = datetime.now(timezone.utc)
            if existing:
                existing.bot_id = worker.bot_id
                existing.name = worker.name
                existing.description = worker.description
                existing.worker_prompt = worker.worker_prompt
                existing.llm_provider = worker.llm_provider
                existing.llm_model = worker.llm_model
                existing.temperature = worker.temperature
                existing.max_tokens = worker.max_tokens
                existing.max_tool_calls = worker.max_tool_calls
                existing.enabled_mcp_ids = worker.enabled_mcp_ids
                existing.knowledge_base_ids = worker.knowledge_base_ids
                existing.sort_order = worker.sort_order
                existing.updated_at = now
            else:
                model = BotWorkerModel(
                    id=worker.id,
                    bot_id=worker.bot_id,
                    name=worker.name,
                    description=worker.description,
                    worker_prompt=worker.worker_prompt,
                    llm_provider=worker.llm_provider,
                    llm_model=worker.llm_model,
                    temperature=worker.temperature,
                    max_tokens=worker.max_tokens,
                    max_tool_calls=worker.max_tool_calls,
                    enabled_mcp_ids=worker.enabled_mcp_ids,
                    knowledge_base_ids=worker.knowledge_base_ids,
                    sort_order=worker.sort_order,
                    created_at=worker.created_at,
                    updated_at=now,
                )
                self._session.add(model)

    async def find_by_bot_id(
        self, bot_id: str
    ) -> list[WorkerConfig]:
        stmt = (
            select(BotWorkerModel)
            .where(BotWorkerModel.bot_id == bot_id)
            .order_by(BotWorkerModel.sort_order)
        )
        result = await self._session.execute(stmt)
        return [
            self._to_entity(m) for m in result.scalars().all()
        ]

    async def find_by_id(
        self, worker_id: str
    ) -> WorkerConfig | None:
        model = await self._session.get(BotWorkerModel, worker_id)
        return self._to_entity(model) if model else None

    async def delete(self, worker_id: str) -> None:
        async with atomic(self._session):
            existing = await self._session.get(
                BotWorkerModel, worker_id
            )
            if existing:
                await self._session.delete(existing)
