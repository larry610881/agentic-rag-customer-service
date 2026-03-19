from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tenant.entity import Tenant
from src.domain.tenant.repository import TenantRepository
from src.domain.tenant.value_objects import TenantId
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.tenant_model import TenantModel


class SQLAlchemyTenantRepository(TenantRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: TenantModel) -> Tenant:
        return Tenant(
            id=TenantId(value=model.id),
            name=model.name,
            plan=model.plan,
            allowed_agent_modes=(
                list(model.allowed_agent_modes)
                if model.allowed_agent_modes
                else ["router"]
            ),
            monthly_token_limit=model.monthly_token_limit,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, tenant: Tenant) -> None:
        async with atomic(self._session):
            model = TenantModel(
                id=tenant.id.value,
                name=tenant.name,
                plan=tenant.plan,
                allowed_agent_modes=tenant.allowed_agent_modes,
                monthly_token_limit=tenant.monthly_token_limit,
                created_at=tenant.created_at,
                updated_at=tenant.updated_at,
            )
            await self._session.merge(model)

    async def find_by_id(self, tenant_id: str) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.id == tenant_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_name(self, name: str) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.name == name)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_all(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Tenant]:
        stmt = select(TenantModel).order_by(TenantModel.created_at)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_all(self) -> int:
        stmt = select(func.count()).select_from(TenantModel)
        result = await self._session.execute(stmt)
        return result.scalar_one()
