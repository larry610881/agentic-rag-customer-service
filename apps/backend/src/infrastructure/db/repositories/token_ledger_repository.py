"""SQLAlchemy TokenLedger Repository — S-Token-Gov.2"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ledger.entity import TokenLedger
from src.domain.ledger.repository import TokenLedgerRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.token_ledger_model import TokenLedgerModel


class SQLAlchemyTokenLedgerRepository(TokenLedgerRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, m: TokenLedgerModel) -> TokenLedger:
        return TokenLedger(
            id=m.id,
            tenant_id=m.tenant_id,
            cycle_year_month=m.cycle_year_month,
            plan_name=m.plan_name,
            base_total=m.base_total,
            base_remaining=m.base_remaining,
            addon_remaining=m.addon_remaining,
            total_used_in_cycle=m.total_used_in_cycle,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    async def save(self, ledger: TokenLedger) -> TokenLedger:
        async with atomic(self._session):
            existing = await self._session.get(TokenLedgerModel, ledger.id)
            if existing:
                existing.tenant_id = ledger.tenant_id
                existing.cycle_year_month = ledger.cycle_year_month
                existing.plan_name = ledger.plan_name
                existing.base_total = ledger.base_total
                existing.base_remaining = ledger.base_remaining
                existing.addon_remaining = ledger.addon_remaining
                existing.total_used_in_cycle = ledger.total_used_in_cycle
                existing.updated_at = datetime.now(timezone.utc)
            else:
                model = TokenLedgerModel(
                    id=ledger.id,
                    tenant_id=ledger.tenant_id,
                    cycle_year_month=ledger.cycle_year_month,
                    plan_name=ledger.plan_name,
                    base_total=ledger.base_total,
                    base_remaining=ledger.base_remaining,
                    addon_remaining=ledger.addon_remaining,
                    total_used_in_cycle=ledger.total_used_in_cycle,
                    created_at=ledger.created_at,
                    updated_at=ledger.updated_at,
                )
                self._session.add(model)
        return ledger

    async def find_by_tenant_and_cycle(
        self, tenant_id: str, cycle: str
    ) -> TokenLedger | None:
        stmt = select(TokenLedgerModel).where(
            TokenLedgerModel.tenant_id == tenant_id,
            TokenLedgerModel.cycle_year_month == cycle,
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def find_latest_by_tenant(
        self, tenant_id: str
    ) -> TokenLedger | None:
        stmt = (
            select(TokenLedgerModel)
            .where(TokenLedgerModel.tenant_id == tenant_id)
            .order_by(TokenLedgerModel.cycle_year_month.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def find_all_for_cycle(self, cycle: str) -> list[TokenLedger]:
        stmt = select(TokenLedgerModel).where(
            TokenLedgerModel.cycle_year_month == cycle
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]
