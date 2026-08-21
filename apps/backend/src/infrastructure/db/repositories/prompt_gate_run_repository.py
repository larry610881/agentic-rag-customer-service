"""PromptGateRunRepository SQLAlchemy 實作"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.prompt_gate.gate_run_entity import PromptGateRun
from src.domain.prompt_gate.gate_run_repository import (
    PromptGateRunRepository,
)
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.prompt_gate_run_model import (
    PromptGateRunModel,
)

_FIELDS = (
    "tenant_id", "bot_id", "version_id", "status", "verdict",
    "fail_reasons", "dataset_ids", "repeats", "soft_threshold",
    "total_cases", "hard_failed_cases", "soft_pass_rate",
    "unstable_cases", "est_cost", "actual_cost", "input_tokens",
    "output_tokens", "details", "error_message", "triggered_by",
    "created_at", "started_at", "completed_at",
)


class SQLAlchemyPromptGateRunRepository(PromptGateRunRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: PromptGateRunModel) -> PromptGateRun:
        return PromptGateRun(
            id=model.id,
            tenant_id=model.tenant_id,
            bot_id=model.bot_id,
            version_id=model.version_id,
            status=model.status,
            verdict=model.verdict,
            fail_reasons=list(model.fail_reasons or []),
            dataset_ids=list(model.dataset_ids or []),
            repeats=model.repeats,
            soft_threshold=model.soft_threshold,
            total_cases=model.total_cases,
            hard_failed_cases=model.hard_failed_cases,
            soft_pass_rate=model.soft_pass_rate,
            unstable_cases=model.unstable_cases,
            est_cost=model.est_cost,
            actual_cost=model.actual_cost,
            input_tokens=model.input_tokens,
            output_tokens=model.output_tokens,
            details=model.details,
            error_message=model.error_message,
            triggered_by=model.triggered_by,
            created_at=model.created_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
        )

    async def save(self, run: PromptGateRun) -> None:
        async with atomic(self._session):
            existing = await self._session.get(PromptGateRunModel, run.id)
            if existing:
                for f in _FIELDS:
                    setattr(existing, f, getattr(run, f))
            else:
                self._session.add(
                    PromptGateRunModel(
                        id=run.id,
                        **{f: getattr(run, f) for f in _FIELDS},
                    )
                )

    async def find_by_id(
        self, run_id: str, tenant_id: str
    ) -> PromptGateRun | None:
        stmt = select(PromptGateRunModel).where(
            PromptGateRunModel.id == run_id,
            PromptGateRunModel.tenant_id == tenant_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def count_today(self, bot_id: str) -> int:
        day_start = datetime.combine(
            datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc
        )
        stmt = (
            select(func.count())
            .select_from(PromptGateRunModel)
            .where(
                PromptGateRunModel.bot_id == bot_id,
                PromptGateRunModel.created_at >= day_start,
            )
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def mark_orphans_error(
        self, *, grace_minutes: int = 30
    ) -> list[str]:
        # M7：多實例／滾動部署時，新實例啟動的孤兒清理不得殺掉舊實例上仍健康
        # 執行中的 run。加 created_at 寬限窗：只清超過 grace_minutes（遠長於任何
        # 真實 gate run 時長）的 run，剛啟動的 run 視為其他實例仍在跑、不動。
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=grace_minutes)
        cond = (
            PromptGateRunModel.status.in_(("queued", "running")),
            PromptGateRunModel.created_at < cutoff,
        )
        async with atomic(self._session):
            stmt = select(PromptGateRunModel.version_id).where(*cond)
            version_ids = list(
                (await self._session.execute(stmt)).scalars().all()
            )
            if version_ids:
                await self._session.execute(
                    update(PromptGateRunModel)
                    .where(*cond)
                    .values(
                        status="error",
                        error_message="orphaned by process restart",
                        completed_at=datetime.now(timezone.utc),
                    )
                )
            return version_ids
