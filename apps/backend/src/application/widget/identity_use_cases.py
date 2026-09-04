"""宿主身分綁定用例（Issue #68 P7b）"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog

from src.domain.abuse.policy import AbuseSubject, SubjectKind
from src.domain.platform.services import EncryptionService
from src.domain.widget.identity import (
    TenantIdentitySecret,
    TenantIdentitySecretRepository,
    generate_identity_secret,
    verify_identity,
)

logger = structlog.get_logger(__name__)

AUDIT_ENTITY = "widget_identity"


@dataclass(frozen=True)
class IdentitySecretStatus:
    tenant_id: str
    has_secret: bool
    is_enabled: bool
    enforce_verified: bool
    rotated_at: datetime | None


class GetIdentitySecretStatusUseCase:
    def __init__(self, repo: TenantIdentitySecretRepository) -> None:
        self._repo = repo

    async def execute(self, tenant_id: str) -> IdentitySecretStatus:
        row = await self._repo.get(tenant_id)
        return IdentitySecretStatus(
            tenant_id=tenant_id,
            has_secret=row is not None,
            is_enabled=row.is_enabled if row else False,
            enforce_verified=row.enforce_verified if row else False,
            rotated_at=row.rotated_at if row else None,
        )


class RotateIdentitySecretUseCase:
    """產生新 secret（只回傳這一次）、加密存放、寫稽核。"""

    def __init__(
        self,
        repo: TenantIdentitySecretRepository,
        encryption: EncryptionService,
        audit: Any | None = None,
    ) -> None:
        self._repo = repo
        self._enc = encryption
        self._audit = audit

    async def execute(self, tenant_id: str, *, actor_user_id: str | None) -> str:
        secret = generate_identity_secret()
        existing = await self._repo.get(tenant_id)
        now = datetime.now(timezone.utc)
        row = TenantIdentitySecret(
            tenant_id=tenant_id,
            secret_encrypted=self._enc.encrypt(secret),
            is_enabled=existing.is_enabled if existing else True,
            enforce_verified=existing.enforce_verified if existing else False,
            rotated_at=now,
            updated_at=now,
        )
        await self._repo.save(row)
        if self._audit is not None:
            await self._audit.record(
                entity_type=AUDIT_ENTITY, entity_id=tenant_id, action="rotate",
                before={
                    "rotated_at": existing.rotated_at.isoformat() if existing else None
                },
                after={"rotated_at": now.isoformat()},
                actor_user_id=actor_user_id, tenant_id=tenant_id,
            )
        return secret


class UpdateIdentityPolicyUseCase:
    def __init__(
        self, repo: TenantIdentitySecretRepository, audit: Any | None = None
    ) -> None:
        self._repo = repo
        self._audit = audit

    async def execute(
        self,
        tenant_id: str,
        *,
        is_enabled: bool | None,
        enforce_verified: bool | None,
        actor_user_id: str | None,
    ) -> IdentitySecretStatus:
        row = await self._repo.get(tenant_id)
        if row is None:
            return IdentitySecretStatus(tenant_id, False, False, False, None)
        before = {
            "is_enabled": row.is_enabled,
            "enforce_verified": row.enforce_verified,
        }
        if is_enabled is not None:
            row.is_enabled = is_enabled
        if enforce_verified is not None:
            row.enforce_verified = enforce_verified
        row.updated_at = datetime.now(timezone.utc)
        await self._repo.save(row)
        if self._audit is not None:
            await self._audit.record(
                entity_type=AUDIT_ENTITY, entity_id=tenant_id, action="update",
                before=before,
                after={
                    "is_enabled": row.is_enabled,
                    "enforce_verified": row.enforce_verified,
                },
                actor_user_id=actor_user_id, tenant_id=tenant_id,
            )
        return IdentitySecretStatus(
            tenant_id, True, row.is_enabled, row.enforce_verified, row.rotated_at
        )


@dataclass(frozen=True)
class IdentityVerdict:
    verified: bool
    enforce: bool          # 租戶是否強制驗證（失敗時要不要拒絕）
    reason: str = ""       # not_configured | disabled | invalid


class VerifyWidgetIdentityUseCase:
    """驗宿主簽章；失敗計 identify_fail（fail-open：儲存失效視為未設定）。"""

    def __init__(
        self,
        repo: TenantIdentitySecretRepository,
        encryption: EncryptionService,
        abuse_control: Any | None = None,
    ) -> None:
        self._repo = repo
        self._enc = encryption
        self._abuse = abuse_control

    async def execute(
        self,
        *,
        tenant_id: str,
        visitor_id: str | None,
        user_id: str,
        exp: int,
        presented_hash: str,
    ) -> IdentityVerdict:
        try:
            row = await self._repo.get(tenant_id)
        except Exception:
            logger.warning("widget_identity.repo_unavailable", tenant_id=tenant_id)
            return IdentityVerdict(False, False, "not_configured")
        if row is None:
            return IdentityVerdict(False, False, "not_configured")
        if not row.is_enabled:
            return IdentityVerdict(False, False, "disabled")
        try:
            secret = self._enc.decrypt(row.secret_encrypted)
        except Exception:
            logger.warning("widget_identity.decrypt_failed", tenant_id=tenant_id)
            return IdentityVerdict(False, row.enforce_verified, "invalid")
        if verify_identity(secret, user_id, exp, presented_hash):
            return IdentityVerdict(True, row.enforce_verified)
        if self._abuse is not None and visitor_id:
            try:
                await self._abuse.record(
                    tenant_id, AbuseSubject(SubjectKind.VISITOR, visitor_id),
                    identify_fail=True, channel="widget",
                )
            except Exception:
                logger.warning("widget_identity.abuse_record_failed")
        return IdentityVerdict(False, row.enforce_verified, "invalid")
