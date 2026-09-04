"""異常控管設定與受控清單用例（Issue #68 P7c）

設計（Larry 2026-09-04）：系統層一份預設 + 幾個「方案」；每個租戶指定方案或個別微調；
**只有 system_admin 能改**，tenant_admin 只能看自己生效中的設定與受控清單。
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog

from src.domain.abuse.events import mask_subject_id
from src.domain.abuse.policy import AbusePolicy, AbuseSubject, SubjectKind
from src.domain.abuse.settings import (
    BUILTIN_PROFILES,
    DEFAULT_PROFILE,
    PLATFORM_SCOPE_ID,
    PROFILE_KEY,
    SCOPE_PLATFORM,
    SCOPE_PROFILE,
    SCOPE_TENANT,
    AbuseSettings,
    AbuseSettingsRepository,
    policy_view,
    resolve_policy,
    validate_overrides,
)
from src.domain.abuse.store import AbuseScoreStore
from src.domain.shared.exceptions import ValidationError

logger = structlog.get_logger(__name__)

AUDIT_ENTITY = "abuse_settings"


class CachedAbusePolicyProvider:
    """每租戶生效 policy，程序內快取 60 秒；DB 失效退回預設（fail-open）。"""

    def __init__(
        self,
        repo_factory: Any,
        ttl_seconds: int = 60,
        base_mode_from_env: str | None = None,
    ) -> None:
        self._repo_factory = repo_factory
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[AbusePolicy, float]] = {}
        self._env_mode = base_mode_from_env

    def invalidate(self, tenant_id: str | None = None) -> None:
        if tenant_id is None:
            self._cache.clear()
        else:
            self._cache.pop(tenant_id, None)

    async def policy_for(self, tenant_id: str) -> AbusePolicy:
        cached = self._cache.get(tenant_id)
        if cached and cached[1] > time.monotonic():
            return cached[0]
        try:
            policy = await self._load(tenant_id)
        except Exception:
            logger.warning("abuse_settings.load_failed", tenant_id=tenant_id)
            policy = AbusePolicy()
        self._cache[tenant_id] = (policy, time.monotonic() + self._ttl)
        return policy

    async def _load(self, tenant_id: str) -> AbusePolicy:
        repo: AbuseSettingsRepository = self._repo_factory()
        platform = await repo.get(SCOPE_PLATFORM, PLATFORM_SCOPE_ID)
        tenant = await repo.get(SCOPE_TENANT, tenant_id)
        profiles = {p.scope_id: p.overrides for p in await repo.list_profiles()}
        if platform is None and self._env_mode:
            # 尚未在後台設定時，沿用環境變數的模式（ABUSE_CONTROL_MODE）
            platform = AbuseSettings(
                scope_kind=SCOPE_PLATFORM, scope_id=PLATFORM_SCOPE_ID,
                overrides={"mode": self._env_mode},
            )
        return resolve_policy(platform, tenant, profiles)


@dataclass(frozen=True)
class AbuseSettingsOverview:
    platform_overrides: dict[str, Any]
    profiles: dict[str, dict[str, Any]]
    effective_default: dict[str, Any]


class GetAbuseSettingsOverviewUseCase:
    def __init__(self, repo: AbuseSettingsRepository) -> None:
        self._repo = repo

    async def execute(self) -> AbuseSettingsOverview:
        platform = await self._repo.get(SCOPE_PLATFORM, PLATFORM_SCOPE_ID)
        stored = {p.scope_id: p.overrides for p in await self._repo.list_profiles()}
        profiles = dict(BUILTIN_PROFILES)
        profiles.update(stored)
        return AbuseSettingsOverview(
            platform_overrides=platform.overrides if platform else {},
            profiles=profiles,
            effective_default=policy_view(resolve_policy(platform, None, stored)),
        )


@dataclass(frozen=True)
class TenantAbuseSettings:
    tenant_id: str
    profile: str
    overrides: dict[str, Any]
    effective: dict[str, Any]


class GetTenantAbuseSettingsUseCase:
    def __init__(self, repo: AbuseSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, tenant_id: str) -> TenantAbuseSettings:
        platform = await self._repo.get(SCOPE_PLATFORM, PLATFORM_SCOPE_ID)
        tenant = await self._repo.get(SCOPE_TENANT, tenant_id)
        stored = {p.scope_id: p.overrides for p in await self._repo.list_profiles()}
        overrides = dict(tenant.overrides) if tenant else {}
        profile = str(overrides.pop(PROFILE_KEY, DEFAULT_PROFILE))
        return TenantAbuseSettings(
            tenant_id=tenant_id,
            profile=profile,
            overrides=overrides,
            effective=policy_view(resolve_policy(platform, tenant, stored)),
        )


class UpdateAbuseSettingsUseCase:
    """寫 platform / profile / tenant 任一層（僅 system_admin）。

    驗範圍、寫稽核、清快取。
    """

    def __init__(
        self,
        repo: AbuseSettingsRepository,
        provider: CachedAbusePolicyProvider | None = None,
        audit: Any | None = None,
    ) -> None:
        self._repo = repo
        self._provider = provider
        self._audit = audit

    async def execute(
        self,
        *,
        scope_kind: str,
        scope_id: str,
        overrides: dict[str, Any],
        actor_user_id: str | None,
        profile: str | None = None,
    ) -> AbuseSettings:
        if scope_kind not in (SCOPE_PLATFORM, SCOPE_PROFILE, SCOPE_TENANT):
            raise ValidationError("scope_kind must be platform, profile or tenant")
        if scope_kind == SCOPE_PLATFORM:
            scope_id = PLATFORM_SCOPE_ID
        clean = validate_overrides(overrides)
        if scope_kind == SCOPE_TENANT and profile is not None:
            known = set(BUILTIN_PROFILES) | {
                p.scope_id for p in await self._repo.list_profiles()
            }
            if profile not in known:
                raise ValidationError(f"Unknown profile: {profile}")
            clean[PROFILE_KEY] = profile
        elif PROFILE_KEY in clean and scope_kind != SCOPE_TENANT:
            raise ValidationError("profile can only be assigned at tenant scope")

        existing = await self._repo.get(scope_kind, scope_id)
        before = dict(existing.overrides) if existing else {}
        settings = AbuseSettings(
            scope_kind=scope_kind, scope_id=scope_id, overrides=clean,
            updated_by=actor_user_id, updated_at=datetime.now(timezone.utc),
            id=existing.id if existing else AbuseSettings(
                scope_kind=scope_kind, scope_id=scope_id
            ).id,
        )
        await self._repo.save(settings)
        if self._provider is not None:
            self._provider.invalidate(None if scope_kind != SCOPE_TENANT else scope_id)
        if self._audit is not None:
            await self._audit.record(
                entity_type=AUDIT_ENTITY,
                entity_id=f"{scope_kind}:{scope_id}",
                action="update",
                before=before,
                after=clean,
                actor_user_id=actor_user_id,
                tenant_id=scope_id if scope_kind == SCOPE_TENANT else None,
            )
        return settings


@dataclass(frozen=True)
class ControlledSubject:
    tenant_id: str
    subject_kind: str
    subject_id: str
    subject_masked: str
    level: int
    remaining_seconds: int


class ListAbuseControlsUseCase:
    def __init__(self, store: AbuseScoreStore) -> None:
        self._store = store

    async def execute(self, tenant_id: str | None) -> list[ControlledSubject]:
        prefix = f"abuse:{tenant_id}:" if tenant_id else "abuse:"
        rows = await self._store.list_locked(prefix)
        out: list[ControlledSubject] = []
        for key, level, remaining in rows:
            parts = key.split(":", 3)  # abuse:{tenant}:{kind}:{id}
            if len(parts) != 4:
                continue
            _, tenant, kind, sid = parts
            try:
                SubjectKind(kind)
            except ValueError:
                continue
            out.append(ControlledSubject(
                tenant_id=tenant, subject_kind=kind, subject_id=sid,
                subject_masked=mask_subject_id(sid), level=level,
                remaining_seconds=remaining,
            ))
        out.sort(key=lambda c: (-c.level, -c.remaining_seconds))
        return out


class ReleaseAbuseControlUseCase:
    def __init__(self, control_service: Any) -> None:
        self._control = control_service

    async def execute(
        self, *, tenant_id: str, subject_kind: str, subject_id: str,
        actor_user_id: str | None,
    ) -> None:
        subject = AbuseSubject(SubjectKind(subject_kind), subject_id)
        await self._control.release(tenant_id, subject, actor_user_id=actor_user_id)
