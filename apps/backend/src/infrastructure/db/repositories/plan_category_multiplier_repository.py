"""SQLAlchemy PlanCategoryMultiplier Repository — Issue #74"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.plan.multiplier_repository import PlanCategoryMultiplierRepository
from src.domain.plan.value_objects import PlanCategoryMultiplier
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.plan_category_multiplier_model import (
    PlanCategoryMultiplierModel,
)


class SQLAlchemyPlanCategoryMultiplierRepository(PlanCategoryMultiplierRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_plan(self, plan_id: str) -> list[PlanCategoryMultiplier]:
        stmt = (
            select(PlanCategoryMultiplierModel)
            .where(PlanCategoryMultiplierModel.plan_id == plan_id)
            .order_by(PlanCategoryMultiplierModel.usage_category)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            PlanCategoryMultiplier(
                plan_id=m.plan_id,
                usage_category=m.usage_category,
                multiplier=Decimal(m.multiplier),
            )
            for m in rows
        ]

    async def replace_for_plan(
        self, plan_id: str, multipliers: list[PlanCategoryMultiplier]
    ) -> None:
        async with atomic(self._session):
            await self._session.execute(
                delete(PlanCategoryMultiplierModel).where(
                    PlanCategoryMultiplierModel.plan_id == plan_id
                )
            )
            for m in multipliers:
                self._session.add(
                    PlanCategoryMultiplierModel(
                        plan_id=plan_id,
                        usage_category=m.usage_category,
                        multiplier=m.multiplier,
                    )
                )
