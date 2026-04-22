"""SQLAlchemy ModelPricing Repository — S-Pricing.1"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.pricing.entity import ModelPricing, PricingRecalcAudit
from src.domain.pricing.repository import (
    ModelPricingRepository,
    PricingRecalcAuditRepository,
)
from src.domain.pricing.value_objects import PriceRate, PricingCategory
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.model_pricing_model import (
    ModelPricingModel,
    PricingRecalcAuditModel,
)


def _to_entity(m: ModelPricingModel) -> ModelPricing:
    return ModelPricing(
        id=m.id,
        provider=m.provider,
        model_id=m.model_id,
        display_name=m.display_name,
        category=PricingCategory(m.category),
        rate=PriceRate(
            input_price=float(m.input_price),
            output_price=float(m.output_price),
            cache_read_price=float(m.cache_read_price),
            cache_creation_price=float(m.cache_creation_price),
        ),
        effective_from=m.effective_from,
        effective_to=m.effective_to,
        created_by=m.created_by,
        created_at=m.created_at,
        note=m.note,
    )


class SQLAlchemyModelPricingRepository(ModelPricingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, pricing: ModelPricing) -> None:
        async with atomic(self._session):
            model = ModelPricingModel(
                id=pricing.id,
                provider=pricing.provider,
                model_id=pricing.model_id,
                display_name=pricing.display_name,
                category=pricing.category.value,
                input_price=Decimal(str(pricing.rate.input_price)),
                output_price=Decimal(str(pricing.rate.output_price)),
                cache_read_price=Decimal(str(pricing.rate.cache_read_price)),
                cache_creation_price=Decimal(
                    str(pricing.rate.cache_creation_price)
                ),
                effective_from=pricing.effective_from,
                effective_to=pricing.effective_to,
                created_by=pricing.created_by,
                created_at=pricing.created_at,
                note=pricing.note,
            )
            self._session.add(model)

    async def find_by_id(self, pricing_id: str) -> ModelPricing | None:
        model = await self._session.get(ModelPricingModel, pricing_id)
        return _to_entity(model) if model else None

    async def find_active_version(
        self, provider: str, model_id: str, at: datetime
    ) -> ModelPricing | None:
        stmt = (
            select(ModelPricingModel)
            .where(
                ModelPricingModel.provider == provider,
                ModelPricingModel.model_id == model_id,
                ModelPricingModel.effective_from <= at,
                or_(
                    ModelPricingModel.effective_to.is_(None),
                    ModelPricingModel.effective_to > at,
                ),
            )
            .order_by(ModelPricingModel.effective_from.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return _to_entity(m) if m else None

    async def find_all_versions(
        self,
        provider: str | None = None,
        category: str | None = None,
    ) -> list[ModelPricing]:
        stmt = select(ModelPricingModel)
        if provider:
            stmt = stmt.where(ModelPricingModel.provider == provider)
        if category:
            stmt = stmt.where(ModelPricingModel.category == category)
        stmt = stmt.order_by(
            ModelPricingModel.provider,
            ModelPricingModel.model_id,
            ModelPricingModel.effective_from.desc(),
        )
        result = await self._session.execute(stmt)
        return [_to_entity(m) for m in result.scalars().all()]

    async def list_all_for_cache(self) -> list[ModelPricing]:
        stmt = select(ModelPricingModel)
        result = await self._session.execute(stmt)
        return [_to_entity(m) for m in result.scalars().all()]

    async def update_effective_to(
        self, pricing_id: str, effective_to: datetime
    ) -> None:
        async with atomic(self._session):
            await self._session.execute(
                update(ModelPricingModel)
                .where(ModelPricingModel.id == pricing_id)
                .values(effective_to=effective_to)
            )


class SQLAlchemyPricingRecalcAuditRepository(PricingRecalcAuditRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, audit: PricingRecalcAudit) -> None:
        async with atomic(self._session):
            model = PricingRecalcAuditModel(
                id=audit.id,
                pricing_id=audit.pricing_id,
                recalc_from=audit.recalc_from,
                recalc_to=audit.recalc_to,
                affected_rows=audit.affected_rows,
                cost_before_total=Decimal(str(audit.cost_before_total)),
                cost_after_total=Decimal(str(audit.cost_after_total)),
                executed_by=audit.executed_by,
                executed_at=audit.executed_at,
                reason=audit.reason,
            )
            self._session.add(model)

    async def list_recent(self, limit: int = 100) -> list[PricingRecalcAudit]:
        stmt = (
            select(PricingRecalcAuditModel)
            .order_by(PricingRecalcAuditModel.executed_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            PricingRecalcAudit(
                id=m.id,
                pricing_id=m.pricing_id,
                recalc_from=m.recalc_from,
                recalc_to=m.recalc_to,
                affected_rows=m.affected_rows,
                cost_before_total=float(m.cost_before_total),
                cost_after_total=float(m.cost_after_total),
                executed_by=m.executed_by,
                executed_at=m.executed_at,
                reason=m.reason,
            )
            for m in result.scalars().all()
        ]
