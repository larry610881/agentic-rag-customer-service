"""SQLAlchemy implementation of OptimizationRunRepository."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.eval_dataset.run_entity import OptimizationIteration
from src.domain.eval_dataset.run_repository import OptimizationRunRepository
from src.infrastructure.db.models.prompt_opt_run_model import PromptOptRunModel


class SQLAlchemyOptimizationRunRepository(OptimizationRunRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_iteration(self, iteration: OptimizationIteration) -> None:
        record_id = iteration.id or str(uuid.uuid4())
        model = PromptOptRunModel(
            id=record_id,
            run_id=iteration.run_id,
            iteration=iteration.iteration,
            tenant_id=iteration.tenant_id,
            target_field=iteration.target_field,
            bot_id=iteration.bot_id,
            prompt_snapshot=iteration.prompt_snapshot,
            score=iteration.score,
            passed_count=iteration.passed_count,
            total_count=iteration.total_count,
            is_best=iteration.is_best,
            details=iteration.details,
            created_at=iteration.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_iterations(self, run_id: str) -> list[OptimizationIteration]:
        stmt = (
            select(PromptOptRunModel)
            .where(PromptOptRunModel.run_id == run_id)
            .order_by(PromptOptRunModel.iteration)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_entity(r) for r in rows]

    async def get_best_iteration(
        self, run_id: str
    ) -> OptimizationIteration | None:
        stmt = (
            select(PromptOptRunModel)
            .where(
                PromptOptRunModel.run_id == run_id,
                PromptOptRunModel.is_best.is_(True),
            )
            .order_by(PromptOptRunModel.score.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_runs(
        self,
        tenant_id: str | None = None,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        base_where = ""
        params: dict = {"limit": limit, "offset": offset}
        if tenant_id:
            base_where = "WHERE tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id

        query = text(f"""
            SELECT run_id, tenant_id, target_field, bot_id,
                   MAX(CASE WHEN iteration = 0 THEN score ELSE NULL END) as baseline_score,
                   MAX(CASE WHEN is_best THEN score ELSE 0 END) as best_score,
                   MAX(iteration) as total_iterations,
                   MIN(created_at) as started_at,
                   MAX(created_at) as last_updated_at,
                   MAX(CASE WHEN details IS NOT NULL THEN details->>'type' ELSE NULL END) as run_type
            FROM prompt_opt_runs
            {base_where}
            GROUP BY run_id, tenant_id, target_field, bot_id
            ORDER BY started_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await self._session.execute(query, params)
        return [dict(row._mapping) for row in result]

    async def count_runs(self, tenant_id: str | None = None) -> int:
        if tenant_id:
            query = text("""
                SELECT COUNT(DISTINCT run_id) FROM prompt_opt_runs
                WHERE tenant_id = :tenant_id
            """)
            result = await self._session.execute(query, {"tenant_id": tenant_id})
        else:
            query = text("SELECT COUNT(DISTINCT run_id) FROM prompt_opt_runs")
            result = await self._session.execute(query)
        row = result.scalar()
        return row or 0

    def _to_entity(self, model: PromptOptRunModel) -> OptimizationIteration:
        return OptimizationIteration(
            id=model.id,
            run_id=model.run_id,
            iteration=model.iteration,
            tenant_id=model.tenant_id,
            target_field=model.target_field,
            bot_id=model.bot_id,
            prompt_snapshot=model.prompt_snapshot,
            score=model.score,
            passed_count=model.passed_count,
            total_count=model.total_count,
            is_best=model.is_best,
            details=model.details,
            created_at=model.created_at,
        )
