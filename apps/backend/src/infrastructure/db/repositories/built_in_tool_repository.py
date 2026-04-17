"""Built-in tool repository (PostgreSQL) — mirror of SQLAlchemyMcpServerRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.agent.built_in_tool import BuiltInTool, BuiltInToolRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.built_in_tool_model import BuiltInToolModel


class SQLAlchemyBuiltInToolRepository(BuiltInToolRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: BuiltInToolModel) -> BuiltInTool:
        return BuiltInTool(
            name=model.name,
            label=model.label,
            description=model.description or "",
            requires_kb=bool(model.requires_kb),
            scope=model.scope or "global",
            tenant_ids=list(model.tenant_ids or []),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def find_all(self) -> list[BuiltInTool]:
        stmt = select(BuiltInToolModel).order_by(BuiltInToolModel.name)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_accessible(self, tenant_id: str) -> list[BuiltInTool]:
        stmt = (
            select(BuiltInToolModel)
            .where(
                or_(
                    BuiltInToolModel.scope == "global",
                    cast(BuiltInToolModel.tenant_ids, JSONB).contains(
                        [tenant_id]
                    ),
                ),
            )
            .order_by(BuiltInToolModel.name)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_name(self, name: str) -> BuiltInTool | None:
        model = await self._session.get(BuiltInToolModel, name)
        return self._to_entity(model) if model else None

    async def upsert(self, tool: BuiltInTool) -> None:
        async with atomic(self._session):
            existing = await self._session.get(BuiltInToolModel, tool.name)
            now = datetime.now(timezone.utc)
            if existing is None:
                model = BuiltInToolModel(
                    name=tool.name,
                    label=tool.label,
                    description=tool.description,
                    requires_kb=tool.requires_kb,
                    scope=tool.scope,
                    tenant_ids=list(tool.tenant_ids),
                    created_at=tool.created_at,
                    updated_at=now,
                )
                self._session.add(model)
            else:
                existing.label = tool.label
                existing.description = tool.description
                existing.requires_kb = tool.requires_kb
                existing.scope = tool.scope
                existing.tenant_ids = list(tool.tenant_ids)
                existing.updated_at = now

    async def seed_defaults(self, defaults: Iterable[BuiltInTool]) -> None:
        """Idempotent seed:
        - new tool → INSERT with full defaults
        - existing → UPDATE label/description/requires_kb only
          (preserve scope + tenant_ids set by admin)
        """
        async with atomic(self._session):
            now = datetime.now(timezone.utc)
            for d in defaults:
                existing = await self._session.get(BuiltInToolModel, d.name)
                if existing is None:
                    model = BuiltInToolModel(
                        name=d.name,
                        label=d.label,
                        description=d.description,
                        requires_kb=d.requires_kb,
                        scope=d.scope,
                        tenant_ids=list(d.tenant_ids),
                        created_at=now,
                        updated_at=now,
                    )
                    self._session.add(model)
                else:
                    existing.label = d.label
                    existing.description = d.description
                    existing.requires_kb = d.requires_kb
                    existing.updated_at = now
