from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ratelimit.entity import RateLimitConfig
from src.domain.ratelimit.repository import RateLimitConfigRepository
from src.domain.ratelimit.value_objects import EndpointGroup, RateLimitConfigId
from src.infrastructure.db.models.rate_limit_config_model import (
    RateLimitConfigModel,
)


class SQLAlchemyRateLimitConfigRepository(RateLimitConfigRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: RateLimitConfigModel) -> RateLimitConfig:
        return RateLimitConfig(
            id=RateLimitConfigId(value=model.id),
            tenant_id=model.tenant_id,
            endpoint_group=EndpointGroup(model.endpoint_group),
            requests_per_minute=model.requests_per_minute,
            burst_size=model.burst_size,
            per_user_requests_per_minute=model.per_user_requests_per_minute,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, config: RateLimitConfig) -> None:
        existing = await self._session.get(RateLimitConfigModel, config.id.value)
        if existing:
            existing.tenant_id = config.tenant_id
            existing.endpoint_group = config.endpoint_group.value
            existing.requests_per_minute = config.requests_per_minute
            existing.burst_size = config.burst_size
            existing.per_user_requests_per_minute = (
                config.per_user_requests_per_minute
            )
            existing.updated_at = datetime.now(timezone.utc)
        else:
            model = RateLimitConfigModel(
                id=config.id.value,
                tenant_id=config.tenant_id,
                endpoint_group=config.endpoint_group.value,
                requests_per_minute=config.requests_per_minute,
                burst_size=config.burst_size,
                per_user_requests_per_minute=config.per_user_requests_per_minute,
                created_at=config.created_at,
                updated_at=config.updated_at,
            )
            self._session.add(model)
        await self._session.commit()

    async def find_by_tenant_and_group(
        self, tenant_id: str | None, endpoint_group: str
    ) -> RateLimitConfig | None:
        if tenant_id is None:
            stmt = select(RateLimitConfigModel).where(
                RateLimitConfigModel.tenant_id.is_(None),
                RateLimitConfigModel.endpoint_group == endpoint_group,
            )
        else:
            stmt = select(RateLimitConfigModel).where(
                RateLimitConfigModel.tenant_id == tenant_id,
                RateLimitConfigModel.endpoint_group == endpoint_group,
            )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def find_defaults(self) -> list[RateLimitConfig]:
        stmt = select(RateLimitConfigModel).where(
            RateLimitConfigModel.tenant_id.is_(None)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_all_by_tenant(self, tenant_id: str) -> list[RateLimitConfig]:
        stmt = (
            select(RateLimitConfigModel)
            .where(RateLimitConfigModel.tenant_id == tenant_id)
            .order_by(RateLimitConfigModel.endpoint_group)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def delete(self, config_id: str) -> None:
        await self._session.execute(
            delete(RateLimitConfigModel).where(
                RateLimitConfigModel.id == config_id
            )
        )
        await self._session.commit()
