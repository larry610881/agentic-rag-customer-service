from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.observability.rule_config import (
    DiagnosticRulesConfig,
    DiagnosticRulesConfigRepository,
)
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.diagnostic_rules_config_model import (
    DiagnosticRulesConfigModel,
)


class SQLAlchemyDiagnosticRulesConfigRepository(DiagnosticRulesConfigRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: DiagnosticRulesConfigModel) -> DiagnosticRulesConfig:
        return DiagnosticRulesConfig(
            id=model.id,
            single_rules=model.single_rules or [],
            combo_rules=model.combo_rules or [],
            updated_at=model.updated_at,
        )

    async def get(self) -> DiagnosticRulesConfig | None:
        stmt = select(DiagnosticRulesConfigModel).where(
            DiagnosticRulesConfigModel.id == "default"
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is not None:
            return self._to_entity(model)
        return None

    async def save(self, config: DiagnosticRulesConfig) -> None:
        async with atomic(self._session):
            existing = await self._session.get(
                DiagnosticRulesConfigModel, config.id
            )
            if existing:
                existing.single_rules = config.single_rules
                existing.combo_rules = config.combo_rules
                existing.updated_at = datetime.now(timezone.utc)
            else:
                self._session.add(
                    DiagnosticRulesConfigModel(
                        id=config.id,
                        single_rules=config.single_rules,
                        combo_rules=config.combo_rules,
                        updated_at=config.updated_at,
                    )
                )

    async def delete(self) -> None:
        async with atomic(self._session):
            existing = await self._session.get(
                DiagnosticRulesConfigModel, "default"
            )
            if existing:
                await self._session.delete(existing)
