"""SQLAlchemy Usage Repository 實作"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.usage.entity import UsageRecord
from src.domain.usage.repository import UsageRepository
from src.domain.usage.value_objects import ModelCostStat, UsageSummary
from src.infrastructure.db.models.usage_record_model import UsageRecordModel


class SQLAlchemyUsageRepository(UsageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: UsageRecord) -> None:
        model = UsageRecordModel(
            id=record.id,
            tenant_id=record.tenant_id,
            request_type=record.request_type,
            model=record.model,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            total_tokens=record.total_tokens,
            estimated_cost=record.estimated_cost,
            message_id=record.message_id,
            created_at=record.created_at,
        )
        self._session.add(model)
        await self._session.commit()

    async def find_by_tenant(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[UsageRecord]:
        stmt = select(UsageRecordModel).where(
            UsageRecordModel.tenant_id == tenant_id
        )
        if start_date:
            stmt = stmt.where(UsageRecordModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(UsageRecordModel.created_at <= end_date)
        stmt = stmt.order_by(UsageRecordModel.created_at.desc())

        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        return [
            UsageRecord(
                id=r.id,
                tenant_id=r.tenant_id,
                request_type=r.request_type,
                model=r.model,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                total_tokens=r.total_tokens,
                estimated_cost=r.estimated_cost,
                message_id=r.message_id,
                created_at=r.created_at,
            )
            for r in rows
        ]

    async def get_tenant_summary(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> UsageSummary:
        records = await self.find_by_tenant(tenant_id, start_date, end_date)

        total_input = sum(r.input_tokens for r in records)
        total_output = sum(r.output_tokens for r in records)
        total_tokens = sum(r.total_tokens for r in records)
        total_cost = sum(r.estimated_cost for r in records)

        by_model: dict[str, int] = {}
        by_request_type: dict[str, int] = {}
        for r in records:
            by_model[r.model] = by_model.get(r.model, 0) + r.total_tokens
            by_request_type[r.request_type] = (
                by_request_type.get(r.request_type, 0) + r.total_tokens
            )

        return UsageSummary(
            tenant_id=tenant_id,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_tokens,
            total_cost=total_cost,
            by_model=by_model,
            by_request_type=by_request_type,
        )

    async def get_model_cost_stats(
        self, tenant_id: str, days: int = 30
    ) -> list[ModelCostStat]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        records = await self.find_by_tenant(tenant_id, start_date=since)

        model_data: dict[str, dict] = {}
        for r in records:
            if r.model not in model_data:
                model_data[r.model] = {
                    "count": 0,
                    "input": 0,
                    "output": 0,
                    "cost": 0.0,
                }
            d = model_data[r.model]
            d["count"] += 1
            d["input"] += r.input_tokens
            d["output"] += r.output_tokens
            d["cost"] += r.estimated_cost

        return [
            ModelCostStat(
                model=model,
                message_count=d["count"],
                input_tokens=d["input"],
                output_tokens=d["output"],
                avg_latency_ms=0.0,  # latency is on messages, not usage records
                estimated_cost=round(d["cost"], 4),
            )
            for model, d in model_data.items()
        ]
