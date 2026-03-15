from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.memory.entity import VisitorIdentity, VisitorProfile
from src.domain.memory.repository import VisitorProfileRepository
from src.domain.memory.value_objects import VisitorIdentityId, VisitorProfileId
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.visitor_identity_model import VisitorIdentityModel
from src.infrastructure.db.models.visitor_profile_model import VisitorProfileModel


class SQLAlchemyVisitorProfileRepository(VisitorProfileRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_profile_entity(self, model: VisitorProfileModel) -> VisitorProfile:
        return VisitorProfile(
            id=VisitorProfileId(value=model.id),
            tenant_id=model.tenant_id,
            display_name=model.display_name,
            identities=[],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_identity_entity(self, model: VisitorIdentityModel) -> VisitorIdentity:
        return VisitorIdentity(
            id=VisitorIdentityId(value=model.id),
            profile_id=model.profile_id,
            tenant_id=model.tenant_id,
            source=model.source,
            external_id=model.external_id,
            created_at=model.created_at,
        )

    async def save(self, profile: VisitorProfile) -> None:
        async with atomic(self._session):
            existing = await self._session.get(
                VisitorProfileModel, profile.id.value
            )
            if existing:
                existing.display_name = profile.display_name
                existing.updated_at = datetime.now(timezone.utc)
            else:
                model = VisitorProfileModel(
                    id=profile.id.value,
                    tenant_id=profile.tenant_id,
                    display_name=profile.display_name,
                    created_at=profile.created_at,
                    updated_at=profile.updated_at,
                )
                self._session.add(model)

    async def find_by_id(self, profile_id: str) -> VisitorProfile | None:
        model = await self._session.get(VisitorProfileModel, profile_id)
        if model is None:
            return None
        profile = self._to_profile_entity(model)
        # Load identities
        stmt = select(VisitorIdentityModel).where(
            VisitorIdentityModel.profile_id == profile_id
        )
        result = await self._session.execute(stmt)
        profile.identities = [
            self._to_identity_entity(m) for m in result.scalars().all()
        ]
        return profile

    async def find_identity(
        self, tenant_id: str, source: str, external_id: str
    ) -> VisitorIdentity | None:
        stmt = select(VisitorIdentityModel).where(
            VisitorIdentityModel.tenant_id == tenant_id,
            VisitorIdentityModel.source == source,
            VisitorIdentityModel.external_id == external_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_identity_entity(model)

    async def save_identity(self, identity: VisitorIdentity) -> None:
        async with atomic(self._session):
            model = VisitorIdentityModel(
                id=identity.id.value,
                profile_id=identity.profile_id,
                tenant_id=identity.tenant_id,
                source=identity.source,
                external_id=identity.external_id,
                created_at=identity.created_at,
            )
            await self._session.merge(model)
