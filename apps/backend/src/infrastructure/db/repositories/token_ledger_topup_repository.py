"""SQLAlchemy TokenLedgerTopup Repository — S-Ledger-Unification P1"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ledger.topup_entity import TokenLedgerTopup
from src.domain.ledger.topup_repository import TokenLedgerTopupRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.token_ledger_topup_model import (
    TokenLedgerTopupModel,
)


class SQLAlchemyTokenLedgerTopupRepository(TokenLedgerTopupRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, m: TokenLedgerTopupModel) -> TokenLedgerTopup:
        return TokenLedgerTopup(
            id=m.id,
            tenant_id=m.tenant_id,
            cycle_year_month=m.cycle_year_month,
            amount=m.amount,
            reason=m.reason,
            pricing_version=m.pricing_version,
            created_at=m.created_at,
        )

    async def save(self, topup: TokenLedgerTopup) -> TokenLedgerTopup:
        async with atomic(self._session):
            model = TokenLedgerTopupModel(
                id=topup.id,
                tenant_id=topup.tenant_id,
                cycle_year_month=topup.cycle_year_month,
                amount=topup.amount,
                reason=topup.reason,
                pricing_version=topup.pricing_version,
                created_at=topup.created_at,
            )
            self._session.add(model)
        return topup

    async def sum_amount_in_cycle(
        self, tenant_id: str, cycle_year_month: str
    ) -> int:
        stmt = select(
            func.coalesce(func.sum(TokenLedgerTopupModel.amount), 0)
        ).where(
            TokenLedgerTopupModel.tenant_id == tenant_id,
            TokenLedgerTopupModel.cycle_year_month == cycle_year_month,
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def find_in_cycle(
        self, tenant_id: str, cycle_year_month: str
    ) -> list[TokenLedgerTopup]:
        stmt = (
            select(TokenLedgerTopupModel)
            .where(
                TokenLedgerTopupModel.tenant_id == tenant_id,
                TokenLedgerTopupModel.cycle_year_month == cycle_year_month,
            )
            .order_by(TokenLedgerTopupModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]
