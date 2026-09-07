"""分層設定（platform / profile / tenant）SQLAlchemy 共用實作（Issue #75）

abuse_settings 與 guard_settings 兩張表欄位完全相同（id / scope_kind / scope_id /
overrides / updated_by / updated_at + scope 唯一鍵）；子類別只指定 model 與 entity。
"""

from __future__ import annotations

from typing import Any, ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.settings.layered import SCOPE_PROFILE, LayeredSettings
from src.infrastructure.db.atomic import atomic


class SQLAlchemyLayeredSettingsRepository:
    model_cls: ClassVar[Any]
    entity_cls: ClassVar[type[LayeredSettings]]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @classmethod
    def _to_entity(cls, m: Any) -> Any:
        return cls.entity_cls(
            id=m.id,
            scope_kind=m.scope_kind,
            scope_id=m.scope_id,
            overrides=dict(m.overrides or {}),
            updated_by=m.updated_by,
            updated_at=m.updated_at,
        )

    async def get(self, scope_kind: str, scope_id: str) -> Any | None:
        model = self.model_cls
        stmt = select(model).where(
            model.scope_kind == scope_kind, model.scope_id == scope_id,
        )
        m = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(m) if m is not None else None

    async def save(self, settings: Any) -> None:
        model = self.model_cls
        async with atomic(self._session):
            stmt = select(model).where(
                model.scope_kind == settings.scope_kind,
                model.scope_id == settings.scope_id,
            )
            existing = (await self._session.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                existing.overrides = dict(settings.overrides)
                existing.updated_by = settings.updated_by
                existing.updated_at = settings.updated_at
                return
            self._session.add(model(
                id=settings.id,
                scope_kind=settings.scope_kind,
                scope_id=settings.scope_id,
                overrides=dict(settings.overrides),
                updated_by=settings.updated_by,
                updated_at=settings.updated_at,
            ))

    async def list_profiles(self) -> list[Any]:
        model = self.model_cls
        stmt = (
            select(model)
            .where(model.scope_kind == SCOPE_PROFILE)
            .order_by(model.scope_id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(m) for m in rows]
