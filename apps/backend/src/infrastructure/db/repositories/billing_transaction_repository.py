"""SQLAlchemy BillingTransaction Repository — S-Token-Gov.3"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
