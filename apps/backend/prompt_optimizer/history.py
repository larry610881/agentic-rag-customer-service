"""Optimization run history persistence."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RunHistoryClient:
    """Persists and queries optimization run history."""

    def __init__(self, db_url: str):
        sync_url = db_url.replace("+asyncpg", "").replace("+aiosqlite", "")
        self._engine = create_engine(sync_url)

    def save_iteration(
        self,
        run_id: str,
        iteration: int,
        tenant_id: str,
        target_field: str,
        bot_id: str | None,
        prompt_snapshot: str,
        score: float,
        passed_count: int,
        total_count: int,
        is_best: bool = False,
        details: dict | None = None,
    ) -> str:
        """Save one iteration result."""
        record_id = str(uuid.uuid4())
        query = text("""
            INSERT INTO prompt_opt_runs
            (id, run_id, iteration, tenant_id, target_field, bot_id,
             prompt_snapshot, score, passed_count, total_count, is_best, details, created_at)
            VALUES (:id, :run_id, :iteration, :tenant_id, :target_field, :bot_id,
                    :prompt_snapshot, :score, :passed_count, :total_count, :is_best,
                    CAST(:details AS JSON), NOW())
        """)
        with Session(self._engine) as session:
            session.execute(
                query,
                {
                    "id": record_id,
                    "run_id": run_id,
                    "iteration": iteration,
                    "tenant_id": tenant_id,
                    "target_field": target_field,
                    "bot_id": bot_id,
                    "prompt_snapshot": prompt_snapshot,
                    "score": score,
                    "passed_count": passed_count,
                    "total_count": total_count,
                    "is_best": is_best,
                    "details": str(details) if details else None,
                },
            )
            session.commit()
        return record_id

    def get_run(self, run_id: str) -> list[dict]:
        """Get all iterations for a run, ordered by iteration."""
        query = text("""
            SELECT id, run_id, iteration, tenant_id, target_field, bot_id,
                   prompt_snapshot, score, passed_count, total_count, is_best, details, created_at
            FROM prompt_opt_runs
            WHERE run_id = :run_id
            ORDER BY iteration
        """)
        with Session(self._engine) as session:
            result = session.execute(query, {"run_id": run_id})
            return [dict(row._mapping) for row in result]

    def get_best_prompt(self, run_id: str) -> str | None:
        """Get the best prompt from a run."""
        query = text("""
            SELECT prompt_snapshot FROM prompt_opt_runs
            WHERE run_id = :run_id AND is_best = TRUE
            ORDER BY score DESC LIMIT 1
        """)
        with Session(self._engine) as session:
            result = session.execute(query, {"run_id": run_id})
            row = result.fetchone()
            return row[0] if row else None

    def list_runs(self, tenant_id: str | None = None, limit: int = 20) -> list[dict]:
        """List recent runs with their best scores."""
        if tenant_id:
            query = text("""
                SELECT DISTINCT run_id, tenant_id, target_field, bot_id,
                       MAX(score) as best_score, MAX(iteration) as total_iterations,
                       MIN(created_at) as started_at
                FROM prompt_opt_runs
                WHERE tenant_id = :tenant_id
                GROUP BY run_id, tenant_id, target_field, bot_id
                ORDER BY started_at DESC
                LIMIT :limit
            """)
            params = {"tenant_id": tenant_id, "limit": limit}
        else:
            query = text("""
                SELECT DISTINCT run_id, tenant_id, target_field, bot_id,
                       MAX(score) as best_score, MAX(iteration) as total_iterations,
                       MIN(created_at) as started_at
                FROM prompt_opt_runs
                GROUP BY run_id, tenant_id, target_field, bot_id
                ORDER BY started_at DESC
                LIMIT :limit
            """)
            params = {"limit": limit}

        with Session(self._engine) as session:
            result = session.execute(query, params)
            return [dict(row._mapping) for row in result]

    def close(self) -> None:
        self._engine.dispose()
