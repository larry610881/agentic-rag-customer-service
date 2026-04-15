from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.security.guard_config import GuardRulesConfig, GuardRulesConfigRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.guard_rules_config_model import GuardRulesConfigModel


class SQLAlchemyGuardRulesConfigRepository(GuardRulesConfigRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> GuardRulesConfig | None:
        stmt = select(GuardRulesConfigModel).where(
            GuardRulesConfigModel.id == "default"
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return GuardRulesConfig(
            id=model.id,
            input_rules=model.input_rules or [],
            output_keywords=model.output_keywords or [],
            llm_guard_enabled=model.llm_guard_enabled,
            llm_guard_model=model.llm_guard_model,
            input_guard_prompt=model.input_guard_prompt,
            output_guard_prompt=model.output_guard_prompt,
            blocked_response=model.blocked_response,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, config: GuardRulesConfig) -> None:
        async with atomic(self._session):
            model = GuardRulesConfigModel(
                id=config.id,
                input_rules=config.input_rules,
                output_keywords=config.output_keywords,
                llm_guard_enabled=config.llm_guard_enabled,
                llm_guard_model=config.llm_guard_model,
                input_guard_prompt=config.input_guard_prompt,
                output_guard_prompt=config.output_guard_prompt,
                blocked_response=config.blocked_response,
            )
            await self._session.merge(model)
