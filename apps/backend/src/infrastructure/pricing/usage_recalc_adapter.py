"""UsageRecalcPort 實作 — 讀寫 token_usage_records 供 Pricing recalculate 用。

為了避免 Pricing context 引用 Usage entity，此 adapter 直接操作 ORM model，
並以 domain/pricing/repository.py 的 UsageRecalcRow DTO 回傳。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.pricing.repository import UsageRecalcPort, UsageRecalcRow
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.usage_record_model import UsageRecordModel


class SQLAlchemyUsageRecalcAdapter(UsageRecalcPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_for_recalc(
        self,
        *,
        provider: str,
        model_id: str,
        recalc_from: datetime,
        recalc_to: datetime,
        limit: int,
    ) -> list[UsageRecalcRow]:
        # record_usage_use_case 寫入時 model 可能是 "provider:model_id" 或裸 "model_id"
        # 這裡 WHERE 兩種都抓，與 record_usage_use_case._estimate_cost_from_registry
        # 的 lookup_model 剝前綴邏輯一致。
        prefixed = f"{provider}:{model_id}"
        stmt = (
            select(UsageRecordModel)
            .where(
                UsageRecordModel.created_at >= recalc_from,
                UsageRecordModel.created_at < recalc_to,
                or_(
                    UsageRecordModel.model == prefixed,
                    UsageRecordModel.model == model_id,
                ),
            )
            .order_by(UsageRecordModel.created_at)
            .limit(limit + 1)  # +1 確認是否超過 limit
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        if len(rows) > limit:
            # 回傳 limit+1 行讓上層偵測超過
            return [_to_row(m) for m in rows[: limit + 1]]
        return [_to_row(m) for m in rows]

    async def bulk_update_cost(
        self,
        *,
        updates: list[tuple[str, float]],
        recalc_at: datetime,
    ) -> None:
        if not updates:
            return
        async with atomic(self._session):
            for row_id, new_cost in updates:
                await self._session.execute(
                    update(UsageRecordModel)
                    .where(UsageRecordModel.id == row_id)
                    .values(
                        estimated_cost=new_cost,
                        cost_recalc_at=recalc_at,
                    )
                )


def _to_row(m: UsageRecordModel) -> UsageRecalcRow:
    return UsageRecalcRow(
        id=m.id,
        model=m.model,
        input_tokens=m.input_tokens,
        output_tokens=m.output_tokens,
        cache_read_tokens=m.cache_read_tokens,
        cache_creation_tokens=m.cache_creation_tokens,
        estimated_cost=float(m.estimated_cost),
    )
