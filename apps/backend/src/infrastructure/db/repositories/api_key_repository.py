from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.auth.api_key import ApiKey
from src.domain.auth.api_key_repository import ApiKeyRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.api_key_model import ApiKeyModel


class SQLAlchemyApiKeyRepository(ApiKeyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_entity(m: ApiKeyModel) -> ApiKey:
        return ApiKey(
            id=m.id,
            tenant_id=m.tenant_id,
            name=m.name,
            description=m.description,
            secret_hash=m.secret_hash,
            secret_salt=m.secret_salt,
            secret_prefix=m.secret_prefix,
            scopes=list(m.scopes or []),
            allowed_bot_ids=list(m.allowed_bot_ids or []),
            expires_at=m.expires_at,
            revoked_at=m.revoked_at,
            token_version=m.token_version,
            last_used_at=m.last_used_at,
            created_by=m.created_by,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    async def save(self, key: ApiKey) -> None:
        async with atomic(self._session):
            existing = await self._session.get(ApiKeyModel, key.id)
            if existing is not None:
                existing.name = key.name
                existing.description = key.description
                existing.scopes = list(key.scopes)
                existing.allowed_bot_ids = list(key.allowed_bot_ids)
                existing.expires_at = key.expires_at
                existing.revoked_at = key.revoked_at
                existing.token_version = key.token_version
                existing.updated_at = key.updated_at
                return
            self._session.add(ApiKeyModel(
                id=key.id,
                tenant_id=key.tenant_id,
                name=key.name,
                description=key.description,
                secret_hash=key.secret_hash,
                secret_salt=key.secret_salt,
                secret_prefix=key.secret_prefix,
                scopes=list(key.scopes),
                allowed_bot_ids=list(key.allowed_bot_ids),
                expires_at=key.expires_at,
                revoked_at=key.revoked_at,
                token_version=key.token_version,
                last_used_at=key.last_used_at,
                created_by=key.created_by,
                created_at=key.created_at,
                updated_at=key.updated_at,
            ))

    async def find_by_id(self, key_id: str) -> ApiKey | None:
        m = await self._session.get(ApiKeyModel, key_id)
        return self._to_entity(m) if m is not None else None

    async def list_by_tenant(self, tenant_id: str) -> list[ApiKey]:
        stmt = (
            select(ApiKeyModel)
            .where(ApiKeyModel.tenant_id == tenant_id)
            .order_by(ApiKeyModel.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(m) for m in rows]

    async def list_all(self) -> list[ApiKey]:
        stmt = select(ApiKeyModel).order_by(ApiKeyModel.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(m) for m in rows]

    async def touch_last_used(self, key_id: str, when: datetime) -> None:
        async with atomic(self._session):
            await self._session.execute(
                update(ApiKeyModel)
                .where(ApiKeyModel.id == key_id)
                .values(last_used_at=when)
            )
