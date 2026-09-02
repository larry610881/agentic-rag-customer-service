from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.observability.effective_config import ConfigSnapshotRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.agent_trace_model import AgentExecutionTraceModel
from src.infrastructure.db.models.config_snapshot_model import ConfigSnapshotModel


class SQLAlchemyConfigSnapshotRepository(ConfigSnapshotRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure(self, config_hash: str, snapshot: dict, schema: int) -> None:
        async with atomic(self._session):
            stmt = (
                pg_insert(ConfigSnapshotModel)
                .values(
                    hash=config_hash,
                    snapshot=snapshot,
                    snapshot_schema=schema,
                    first_seen_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(index_elements=["hash"])
            )
            await self._session.execute(stmt)

    async def find_by_hash(self, config_hash: str) -> dict | None:
        row = await self._session.get(ConfigSnapshotModel, config_hash)
        if row is None:
            return None
        return {
            "hash": row.hash,
            "snapshot": row.snapshot,
            "schema": row.snapshot_schema,
            "first_seen_at": row.first_seen_at,
        }

    async def timeline_for_bot(self, bot_id: str, limit: int = 50) -> list[dict]:
        t = AgentExecutionTraceModel
        stmt = (
            select(
                t.config_hash,
                func.min(t.created_at).label("first_seen_at"),
                func.max(t.created_at).label("last_seen_at"),
                func.count().label("turns"),
            )
            .where(t.bot_id == bot_id, t.config_hash.is_not(None))
            .group_by(t.config_hash)
            .order_by(func.min(t.created_at).desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "hash": r.config_hash,
                "first_seen_at": r.first_seen_at,
                "last_seen_at": r.last_seen_at,
                "turns": int(r.turns),
            }
            for r in result.all()
        ]
