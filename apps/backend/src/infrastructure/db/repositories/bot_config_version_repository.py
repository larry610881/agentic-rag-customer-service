"""BotConfigVersionRepository SQLAlchemy 實作"""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.prompt_gate.entity import BotConfigVersion
from src.domain.prompt_gate.repository import BotConfigVersionRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.bot_config_version_model import (
    BotConfigVersionModel,
)


class SQLAlchemyBotConfigVersionRepository(BotConfigVersionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(model: BotConfigVersionModel) -> BotConfigVersion:
        return BotConfigVersion(
            id=model.id,
            tenant_id=model.tenant_id,
            bot_id=model.bot_id,
            version_no=model.version_no,
            config_snapshot=dict(model.config_snapshot or {}),
            snapshot_schema=model.snapshot_schema,
            changed_fields=list(model.changed_fields or []),
            status=model.status,
            is_current=model.is_current,
            source=model.source,
            source_run_id=model.source_run_id,
            gate_run_id=model.gate_run_id,
            gate_verdict=model.gate_verdict,
            author_user_id=model.author_user_id,
            published_at=model.published_at,
            created_at=model.created_at,
        )

    async def save(self, version: BotConfigVersion) -> None:
        async with atomic(self._session):
            existing = await self._session.get(
                BotConfigVersionModel, version.id
            )
            if existing:
                # append-only：只有狀態機欄位可變，快照內容不可變
                existing.status = version.status
                existing.is_current = version.is_current
                existing.gate_run_id = version.gate_run_id
                existing.gate_verdict = version.gate_verdict
                existing.published_at = version.published_at
            else:
                self._session.add(
                    BotConfigVersionModel(
                        id=version.id,
                        tenant_id=version.tenant_id,
                        bot_id=version.bot_id,
                        version_no=version.version_no,
                        config_snapshot=version.config_snapshot,
                        snapshot_schema=version.snapshot_schema,
                        changed_fields=version.changed_fields,
                        status=version.status,
                        is_current=version.is_current,
                        source=version.source,
                        source_run_id=version.source_run_id,
                        gate_run_id=version.gate_run_id,
                        gate_verdict=version.gate_verdict,
                        author_user_id=version.author_user_id,
                        published_at=version.published_at,
                        created_at=version.created_at,
                    )
                )

    async def find_by_id(
        self, version_id: str, tenant_id: str
    ) -> BotConfigVersion | None:
        stmt = select(BotConfigVersionModel).where(
            BotConfigVersionModel.id == version_id,
            BotConfigVersionModel.tenant_id == tenant_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(model) if model else None

    def _bot_scope(self, bot_id: str, tenant_id: str, status: str | None):
        conditions = [
            BotConfigVersionModel.bot_id == bot_id,
            BotConfigVersionModel.tenant_id == tenant_id,
        ]
        if status is not None:
            conditions.append(BotConfigVersionModel.status == status)
        return conditions

    async def find_by_bot(
        self,
        bot_id: str,
        tenant_id: str,
        *,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[BotConfigVersion]:
        stmt = (
            select(BotConfigVersionModel)
            .where(*self._bot_scope(bot_id, tenant_id, status))
            .order_by(BotConfigVersionModel.version_no.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        models = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(m) for m in models]

    async def count_by_bot(
        self, bot_id: str, tenant_id: str, *, status: str | None = None
    ) -> int:
        stmt = select(func.count()).select_from(BotConfigVersionModel).where(
            *self._bot_scope(bot_id, tenant_id, status)
        )
        return (await self._session.execute(stmt)).scalar_one()

    async def find_current(self, bot_id: str) -> BotConfigVersion | None:
        stmt = select(BotConfigVersionModel).where(
            BotConfigVersionModel.bot_id == bot_id,
            BotConfigVersionModel.is_current.is_(True),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def next_version_no(self, bot_id: str) -> int:
        stmt = select(
            func.coalesce(func.max(BotConfigVersionModel.version_no), 0)
        ).where(BotConfigVersionModel.bot_id == bot_id)
        return (await self._session.execute(stmt)).scalar_one() + 1

    async def set_current(self, bot_id: str, version_id: str) -> None:
        # 單一交易翻轉：先全部清 False 再設新 current，
        # 順序保證 partial unique index 不變量不被違反
        async with atomic(self._session):
            await self._session.execute(
                update(BotConfigVersionModel)
                .where(
                    BotConfigVersionModel.bot_id == bot_id,
                    BotConfigVersionModel.is_current.is_(True),
                    BotConfigVersionModel.id != version_id,
                )
                .values(is_current=False)
            )
            await self._session.execute(
                update(BotConfigVersionModel)
                .where(BotConfigVersionModel.id == version_id)
                .values(is_current=True)
            )
