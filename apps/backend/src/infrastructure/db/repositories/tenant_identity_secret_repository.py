from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.widget.identity import (
    TenantIdentitySecret,
    TenantIdentitySecretRepository,
)
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.tenant_identity_secret_model import (
    TenantIdentitySecretModel,
)


class SQLAlchemyTenantIdentitySecretRepository(TenantIdentitySecretRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tenant_id: str) -> TenantIdentitySecret | None:
        m = await self._session.get(TenantIdentitySecretModel, tenant_id)
        if m is None:
            return None
        return TenantIdentitySecret(
            tenant_id=m.tenant_id,
            secret_encrypted=m.secret_encrypted,
            is_enabled=m.is_enabled,
            enforce_verified=m.enforce_verified,
            rotated_at=m.rotated_at,
            updated_at=m.updated_at,
        )

    async def save(self, secret: TenantIdentitySecret) -> None:
        async with atomic(self._session):
            existing = await self._session.get(
                TenantIdentitySecretModel, secret.tenant_id
            )
            if existing is not None:
                existing.secret_encrypted = secret.secret_encrypted
                existing.is_enabled = secret.is_enabled
                existing.enforce_verified = secret.enforce_verified
                existing.rotated_at = secret.rotated_at
                existing.updated_at = secret.updated_at
                return
            self._session.add(TenantIdentitySecretModel(
                tenant_id=secret.tenant_id,
                secret_encrypted=secret.secret_encrypted,
                is_enabled=secret.is_enabled,
                enforce_verified=secret.enforce_verified,
                rotated_at=secret.rotated_at,
                updated_at=secret.updated_at,
            ))
