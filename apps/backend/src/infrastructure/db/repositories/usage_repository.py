"""SQLAlchemy Usage Repository 實作"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.usage.entity import UsageRecord
from src.domain.usage.repository import UsageRepository
from src.domain.usage.value_objects import (
    BotUsageStat,
    DailyUsageStat,
    ModelCostStat,
    MonthlyUsageStat,
    UsageSummary,
)
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.message_model import MessageModel
from src.infrastructure.db.models.usage_record_model import UsageRecordModel


class SQLAlchemyUsageRepository(UsageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: UsageRecord) -> None:
        async with atomic(self._session):
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
                bot_id=record.bot_id,
                created_at=record.created_at,
            )
            self._session.add(model)

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
                bot_id=r.bot_id,
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
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[ModelCostStat]:
        stmt = (
            select(
                UsageRecordModel.model,
                func.count().label("cnt"),
                func.sum(UsageRecordModel.input_tokens).label("sum_input"),
                func.sum(UsageRecordModel.output_tokens).label("sum_output"),
                func.sum(UsageRecordModel.estimated_cost).label("sum_cost"),
                func.avg(MessageModel.latency_ms).label("avg_latency"),
            )
            .outerjoin(
                MessageModel,
                UsageRecordModel.message_id == MessageModel.id,
            )
            .where(UsageRecordModel.tenant_id == tenant_id)
        )
        if start_date:
            stmt = stmt.where(UsageRecordModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(UsageRecordModel.created_at < end_date)
        stmt = stmt.group_by(UsageRecordModel.model)

        result = await self._session.execute(stmt)
        rows = result.all()

        return [
            ModelCostStat(
                model=row.model,
                message_count=row.cnt,
                input_tokens=row.sum_input or 0,
                output_tokens=row.sum_output or 0,
                avg_latency_ms=round(float(row.avg_latency or 0), 1),
                estimated_cost=round(float(row.sum_cost or 0), 4),
            )
            for row in rows
        ]

    async def get_bot_usage_stats(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[BotUsageStat]:
        from src.infrastructure.db.models.bot_model import BotModel

        stmt = (
            select(
                UsageRecordModel.bot_id,
                BotModel.name.label("bot_name"),
                UsageRecordModel.model,
                func.count().label("cnt"),
                func.sum(UsageRecordModel.input_tokens).label("sum_input"),
                func.sum(UsageRecordModel.output_tokens).label("sum_output"),
                func.sum(UsageRecordModel.total_tokens).label("sum_total"),
                func.sum(UsageRecordModel.estimated_cost).label("sum_cost"),
            )
            .outerjoin(BotModel, UsageRecordModel.bot_id == BotModel.id)
            .where(UsageRecordModel.tenant_id == tenant_id)
        )
        if start_date:
            stmt = stmt.where(UsageRecordModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(UsageRecordModel.created_at < end_date)
        stmt = stmt.group_by(
            UsageRecordModel.bot_id, BotModel.name, UsageRecordModel.model
        )

        result = await self._session.execute(stmt)
        return [
            BotUsageStat(
                bot_id=row.bot_id,
                bot_name=row.bot_name,
                model=row.model,
                input_tokens=row.sum_input or 0,
                output_tokens=row.sum_output or 0,
                total_tokens=row.sum_total or 0,
                estimated_cost=round(float(row.sum_cost or 0), 4),
                message_count=row.cnt,
            )
            for row in result.all()
        ]

    async def get_daily_usage_stats(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[DailyUsageStat]:
        date_col = func.date(UsageRecordModel.created_at).label("dt")

        stmt = (
            select(
                date_col,
                func.count().label("cnt"),
                func.sum(UsageRecordModel.input_tokens).label("sum_input"),
                func.sum(UsageRecordModel.output_tokens).label("sum_output"),
                func.sum(UsageRecordModel.total_tokens).label("sum_total"),
                func.sum(UsageRecordModel.estimated_cost).label("sum_cost"),
            )
            .where(UsageRecordModel.tenant_id == tenant_id)
        )
        if start_date:
            stmt = stmt.where(UsageRecordModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(UsageRecordModel.created_at < end_date)
        stmt = stmt.group_by(date_col).order_by(date_col)

        result = await self._session.execute(stmt)
        return [
            DailyUsageStat(
                date=str(row.dt),
                input_tokens=row.sum_input or 0,
                output_tokens=row.sum_output or 0,
                total_tokens=row.sum_total or 0,
                estimated_cost=round(float(row.sum_cost or 0), 4),
                message_count=row.cnt,
            )
            for row in result.all()
        ]

    async def get_monthly_usage_stats(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[MonthlyUsageStat]:
        month_col = func.to_char(UsageRecordModel.created_at, 'YYYY-MM').label("month")

        stmt = (
            select(
                month_col,
                func.count().label("cnt"),
                func.sum(UsageRecordModel.input_tokens).label("sum_input"),
                func.sum(UsageRecordModel.output_tokens).label("sum_output"),
                func.sum(UsageRecordModel.total_tokens).label("sum_total"),
                func.sum(UsageRecordModel.estimated_cost).label("sum_cost"),
            )
            .where(UsageRecordModel.tenant_id == tenant_id)
        )
        if start_date:
            stmt = stmt.where(UsageRecordModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(UsageRecordModel.created_at < end_date)
        stmt = stmt.group_by(month_col).order_by(month_col)

        result = await self._session.execute(stmt)
        return [
            MonthlyUsageStat(
                month=row.month,
                input_tokens=row.sum_input or 0,
                output_tokens=row.sum_output or 0,
                total_tokens=row.sum_total or 0,
                estimated_cost=round(float(row.sum_cost or 0), 4),
                message_count=row.cnt,
            )
            for row in result.all()
        ]
