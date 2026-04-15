from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.platform.entity import SystemPromptConfig
from src.domain.platform.repository import SystemPromptConfigRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.system_prompt_config_model import (
    SystemPromptConfigModel,
)


class SQLAlchemySystemPromptConfigRepository(SystemPromptConfigRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: SystemPromptConfigModel) -> SystemPromptConfig:
        return SystemPromptConfig(
            id=model.id,
            system_prompt=model.system_prompt,
            updated_at=model.updated_at,
        )

    async def get(self) -> SystemPromptConfig:
        stmt = select(SystemPromptConfigModel).where(
            SystemPromptConfigModel.id == "default"
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is not None:
            return self._to_entity(model)
        # DB 未 seed — 回傳空值（應透過 seed 腳本初始化）
        return SystemPromptConfig(
            id="default",
            updated_at=datetime.now(timezone.utc),
        )

    async def save(self, config: SystemPromptConfig) -> None:
        async with atomic(self._session):
            existing = await self._session.get(
                SystemPromptConfigModel, config.id
            )
            if existing:
                existing.system_prompt = config.system_prompt
                existing.updated_at = datetime.now(timezone.utc)
            else:
                self._session.add(
                    SystemPromptConfigModel(
                        id=config.id,
                        system_prompt=config.system_prompt,
                        updated_at=config.updated_at,
                    )
                )
