"""SQLAlchemy Plan Repository — S-Token-Gov.1"""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.plan.entity import Plan
from src.domain.plan.repository import PlanRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.plan_model import PlanModel
from src.infrastructure.db.models.tenant_model import TenantModel


class SQLAlchemyPlanRepository(PlanRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, m: PlanModel) -> Plan:
        return Plan(
            id=m.id,
            name=m.name,
            base_monthly_tokens=m.base_monthly_tokens,
            addon_pack_tokens=m.addon_pack_tokens,
            base_price=m.base_price,
            addon_price=m.addon_price,
            currency=m.currency,
            description=m.description,
            is_active=m.is_active,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    async def save(self, plan: Plan) -> Plan:
        async with atomic(self._session):
            existing = await self._session.get(PlanModel, plan.id)
            if existing:
                existing.name = plan.name
                existing.base_monthly_tokens = plan.base_monthly_tokens
                existing.addon_pack_tokens = plan.addon_pack_tokens
                existing.base_price = plan.base_price
                existing.addon_price = plan.addon_price
                existing.currency = plan.currency
                existing.description = plan.description
                existing.is_active = plan.is_active
                existing.updated_at = datetime.now(timezone.utc)
            else:
                model = PlanModel(
                    id=plan.id,
                    name=plan.name,
                    base_monthly_tokens=plan.base_monthly_tokens,
                    addon_pack_tokens=plan.addon_pack_tokens,
                    base_price=plan.base_price,
                    addon_price=plan.addon_price,
                    currency=plan.currency,
                    description=plan.description,
                    is_active=plan.is_active,
                    created_at=plan.created_at,
                    updated_at=plan.updated_at,
                )
                self._session.add(model)
        return plan

    async def find_by_id(self, plan_id: str) -> Plan | None:
        model = await self._session.get(PlanModel, plan_id)
        return self._to_entity(model) if model else None

    async def find_by_name(self, name: str) -> Plan | None:
        stmt = select(PlanModel).where(PlanModel.name == name)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_all(self, *, include_inactive: bool = True) -> list[Plan]:
        stmt = select(PlanModel)
        if not include_inactive:
            stmt = stmt.where(PlanModel.is_active.is_(True))
        stmt = stmt.order_by(PlanModel.base_price)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def delete(self, plan_id: str) -> None:
        async with atomic(self._session):
            await self._session.execute(
                delete(PlanModel).where(PlanModel.id == plan_id)
            )

    async def count_tenants_using_plan(self, plan_name: str) -> int:
        stmt = select(func.count()).select_from(TenantModel).where(
            TenantModel.plan == plan_name
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
