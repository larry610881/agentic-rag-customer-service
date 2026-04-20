"""SQLAlchemy BillingTransaction Repository — S-Token-Gov.3 (+.4 aggregations)"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.billing.aggregates import (
    MonthlyRevenuePoint,
    PlanRevenuePoint,
    TenantRevenuePoint,
)
from src.domain.billing.entity import BillingTransaction
from src.domain.billing.repository import BillingTransactionRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.billing_transaction_model import (
    BillingTransactionModel,
)


class SQLAlchemyBillingTransactionRepository(BillingTransactionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, m: BillingTransactionModel) -> BillingTransaction:
        return BillingTransaction(
            id=m.id,
            tenant_id=m.tenant_id,
            ledger_id=m.ledger_id,
            cycle_year_month=m.cycle_year_month,
            plan_name=m.plan_name,
            transaction_type=m.transaction_type,
            addon_tokens_added=m.addon_tokens_added,
            amount_currency=m.amount_currency,
            amount_value=m.amount_value,
            triggered_by=m.triggered_by,
            reason=m.reason or "",
            created_at=m.created_at,
        )

    async def save(self, tx: BillingTransaction) -> BillingTransaction:
        async with atomic(self._session):
            model = BillingTransactionModel(
                id=tx.id,
                tenant_id=tx.tenant_id,
                ledger_id=tx.ledger_id,
                cycle_year_month=tx.cycle_year_month,
                plan_name=tx.plan_name,
                transaction_type=tx.transaction_type,
                addon_tokens_added=tx.addon_tokens_added,
                amount_currency=tx.amount_currency,
                amount_value=tx.amount_value,
                triggered_by=tx.triggered_by,
                reason=tx.reason or None,
                created_at=tx.created_at,
            )
            self._session.add(model)
        return tx

    async def find_by_tenant_and_cycle(
        self, tenant_id: str, cycle: str
    ) -> list[BillingTransaction]:
        stmt = (
            select(BillingTransactionModel)
            .where(
                BillingTransactionModel.tenant_id == tenant_id,
                BillingTransactionModel.cycle_year_month == cycle,
            )
            .order_by(BillingTransactionModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_recent(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        tenant_id: str | None = None,
    ) -> list[BillingTransaction]:
        stmt = select(BillingTransactionModel).order_by(
            BillingTransactionModel.created_at.desc()
        )
        if tenant_id is not None:
            stmt = stmt.where(BillingTransactionModel.tenant_id == tenant_id)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_recent(
        self, tenant_id: str | None = None
    ) -> int:
        stmt = select(func.count()).select_from(BillingTransactionModel)
        if tenant_id is not None:
            stmt = stmt.where(BillingTransactionModel.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)

    # --- S-Token-Gov.4: Aggregations ---

    async def aggregate_monthly_revenue(
        self,
        *,
        start_cycle: str,
        end_cycle: str,
        tenant_id: str | None = None,
    ) -> list[MonthlyRevenuePoint]:
        cycle_col = BillingTransactionModel.cycle_year_month
        stmt = (
            select(
                cycle_col.label("cycle"),
                func.sum(BillingTransactionModel.amount_value).label("total"),
                func.count().label("cnt"),
                func.sum(BillingTransactionModel.addon_tokens_added).label(
                    "tokens"
                ),
            )
            .where(cycle_col >= start_cycle, cycle_col <= end_cycle)
            .group_by(cycle_col)
            .order_by(cycle_col.asc())
        )
        if tenant_id is not None:
            stmt = stmt.where(
                BillingTransactionModel.tenant_id == tenant_id
            )
        result = await self._session.execute(stmt)
        return [
            MonthlyRevenuePoint(
                cycle_year_month=row.cycle,
                total_amount=Decimal(row.total or 0),
                transaction_count=int(row.cnt or 0),
                addon_tokens_total=int(row.tokens or 0),
            )
            for row in result.all()
        ]

    async def aggregate_by_plan(
        self,
        *,
        start_cycle: str,
        end_cycle: str,
    ) -> list[PlanRevenuePoint]:
        plan_col = BillingTransactionModel.plan_name
        cycle_col = BillingTransactionModel.cycle_year_month
        total_col = func.sum(BillingTransactionModel.amount_value).label(
            "total"
        )
        stmt = (
            select(
                plan_col.label("plan"),
                total_col,
                func.count().label("cnt"),
            )
            .where(cycle_col >= start_cycle, cycle_col <= end_cycle)
            .group_by(plan_col)
            .order_by(total_col.desc())
        )
        result = await self._session.execute(stmt)
        return [
            PlanRevenuePoint(
                plan_name=row.plan,
                total_amount=Decimal(row.total or 0),
                transaction_count=int(row.cnt or 0),
            )
            for row in result.all()
        ]

    async def aggregate_top_tenants(
        self,
        *,
        start_cycle: str,
        end_cycle: str,
        limit: int = 10,
    ) -> list[TenantRevenuePoint]:
        tenant_col = BillingTransactionModel.tenant_id
        cycle_col = BillingTransactionModel.cycle_year_month
        total_col = func.sum(BillingTransactionModel.amount_value).label(
            "total"
        )
        stmt = (
            select(
                tenant_col.label("tid"),
                total_col,
                func.count().label("cnt"),
            )
            .where(cycle_col >= start_cycle, cycle_col <= end_cycle)
            .group_by(tenant_col)
            .order_by(total_col.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            TenantRevenuePoint(
                tenant_id=row.tid,
                total_amount=Decimal(row.total or 0),
                transaction_count=int(row.cnt or 0),
            )
            for row in result.all()
        ]
