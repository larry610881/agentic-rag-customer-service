"""防護階段三層設定用例（Issue #75）

系統層管底線與預設、方案層給預設、租戶層只能加嚴、system_admin 可鎖定租戶；
**只有 system_admin 能寫三層**（bot 自己的 guard_stages 由租戶在 bot 設定改）。
每次寫入都寫稽核；system_admin 對某租戶 scope 的寫入 source="platform"，
該租戶的變更紀錄（#71）看得到、操作者標「平台」。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.application.bot._tenant_guard import ensure_bot_tenant
from src.application.settings.layered_provider import (
    CachedLayeredProvider,
    LayeredSettingsWriter,
)
from src.domain.audit.entity import SOURCE_API
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.security.guard_stages import (
    ALL_STAGES_ON,
    BUILTIN_PROFILES,
    DEFAULT_PROFILE,
    PLATFORM_SCOPE_ID,
    PROFILE_KEY,
    SCOPE_PLATFORM,
    SCOPE_PROFILE,
    SCOPE_TENANT,
    STAGES,
    EffectiveGuard,
    GuardSettings,
    GuardSettingsRepository,
    resolve_guard,
    validate_guard_overrides,
)
from src.domain.settings.layered import merge_profiles
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError

AUDIT_ENTITY = "guard_settings"
SOURCE_PLATFORM = "platform"   # 稽核來源：系統管理員對租戶 scope 的變更
SYSTEM_ADMIN_ROLE = "system_admin"
KEY_LOCKED = "locked"


def _bot_stages(bot: Any) -> list[str] | None:
    """從 Bot（或任何帶 guard_stages 的物件）取 bot 層覆寫；非 list 視為未設定。"""
    stages = getattr(bot, "guard_stages", None) if bot is not None else None
    return list(stages) if isinstance(stages, list) else None


class CachedGuardProvider(CachedLayeredProvider[EffectiveGuard]):
    """每租戶有效防護（不含 bot 層）快取 60 秒；DB 失效 → fail-safe 全部階段開啟。"""

    log_event = "guard_settings.load_failed"

    async def effective_for(self, tenant_id: str, bot: Any = None) -> EffectiveGuard:
        """租戶層解析（快取）+ bot 層疊加（純函式，不快取）。"""
        tenant_level = await self.resolve(tenant_id)
        try:
            return tenant_level.with_bot(_bot_stages(bot))
        except ValidationError:
            # bot 存了未知階段（舊資料）→ 忽略 bot 層，不因此降低防護
            return tenant_level

    def _fallback(self, key: str) -> EffectiveGuard:
        return ALL_STAGES_ON

    async def _load(  # type: ignore[override]
        self, repo: GuardSettingsRepository, tenant_id: str
    ) -> EffectiveGuard:
        platform = await repo.get(SCOPE_PLATFORM, PLATFORM_SCOPE_ID)
        tenant = await repo.get(SCOPE_TENANT, tenant_id)
        profiles = {p.scope_id: p.overrides for p in await repo.list_profiles()}
        return resolve_guard(platform, tenant, profiles)


@dataclass(frozen=True)
class GuardOverview:
    platform_overrides: dict[str, Any]
    profiles: dict[str, dict[str, Any]]
    effective_default: EffectiveGuard


class GetGuardOverviewUseCase:
    def __init__(self, repo: GuardSettingsRepository) -> None:
        self._repo = repo

    async def execute(self) -> GuardOverview:
        platform = await self._repo.get(SCOPE_PLATFORM, PLATFORM_SCOPE_ID)
        stored = await self._repo.list_profiles()
        return GuardOverview(
            platform_overrides=dict(platform.overrides) if platform else {},
            profiles=merge_profiles(BUILTIN_PROFILES, stored),
            effective_default=resolve_guard(
                platform, None, {p.scope_id: p.overrides for p in stored}
            ),
        )


@dataclass(frozen=True)
class TenantGuardSettings:
    tenant_id: str
    profile: str
    overrides: dict[str, Any]
    locked: bool
    effective: EffectiveGuard


class GetTenantGuardUseCase:
    def __init__(self, repo: GuardSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, tenant_id: str) -> TenantGuardSettings:
        platform = await self._repo.get(SCOPE_PLATFORM, PLATFORM_SCOPE_ID)
        tenant = await self._repo.get(SCOPE_TENANT, tenant_id)
        stored = {p.scope_id: p.overrides for p in await self._repo.list_profiles()}
        overrides = dict(tenant.overrides) if tenant else {}
        profile = str(overrides.pop(PROFILE_KEY, DEFAULT_PROFILE))
        locked = bool(overrides.pop(KEY_LOCKED, False))
        return TenantGuardSettings(
            tenant_id=tenant_id,
            profile=profile,
            overrides=overrides,
            locked=locked,
            effective=resolve_guard(platform, tenant, stored),
        )


class UpdateGuardSettingsUseCase:
    """寫 platform / profile / tenant 任一層（僅 system_admin）。

    驗鍵與階段名、寫稽核、清快取；tenant scope 且 actor 為 system_admin 時
    稽核 source="platform"（租戶端變更紀錄標「平台」）。
    """

    def __init__(
        self,
        repo: GuardSettingsRepository,
        provider: CachedGuardProvider | None = None,
        audit: Any | None = None,
    ) -> None:
        self._repo = repo
        self._writer = LayeredSettingsWriter(
            repo, GuardSettings, AUDIT_ENTITY, provider=provider, audit=audit,
        )

    async def execute(
        self,
        *,
        scope_kind: str,
        scope_id: str,
        overrides: dict[str, Any],
        actor_user_id: str | None,
        actor_role: str | None = SYSTEM_ADMIN_ROLE,
        profile: str | None = None,
        locked: bool | None = None,
    ) -> GuardSettings:
        if scope_kind not in (SCOPE_PLATFORM, SCOPE_PROFILE, SCOPE_TENANT):
            raise ValidationError("scope_kind must be platform, profile or tenant")
        merged = dict(overrides)
        if scope_kind == SCOPE_TENANT:
            if profile is not None:
                known = set(BUILTIN_PROFILES) | {
                    p.scope_id for p in await self._repo.list_profiles()
                }
                if profile not in known:
                    raise ValidationError(f"Unknown profile: {profile}")
                merged[PROFILE_KEY] = profile
            if locked is not None:
                merged[KEY_LOCKED] = locked
        elif profile is not None or locked is not None:
            raise ValidationError(
                "profile and locked can only be assigned at tenant scope"
            )
        clean = validate_guard_overrides(merged, scope_kind)
        source = (
            SOURCE_PLATFORM
            if scope_kind == SCOPE_TENANT and actor_role == SYSTEM_ADMIN_ROLE
            else SOURCE_API
        )
        saved: GuardSettings = await self._writer.write(
            scope_kind=scope_kind, scope_id=scope_id, overrides=clean,
            actor_user_id=actor_user_id, source=source,
        )
        return saved


@dataclass(frozen=True)
class EffectiveGuardView:
    tenant_id: str
    bot_id: str
    effective: EffectiveGuard
    bot_stages: list[str] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "bot_id": self.bot_id,
            **self.effective.view(),
            "bot_stages": self.bot_stages,
            "available_stages": list(STAGES),
        }


class GetEffectiveGuardUseCase:
    """租戶端讀取某 bot 的有效防護（歸屬檢查與 GetBot 一致：跨租戶 → 404）。"""

    def __init__(
        self, bot_repository: BotRepository, provider: CachedGuardProvider
    ) -> None:
        self._bot_repo = bot_repository
        self._provider = provider

    async def execute(
        self, bot_id: str, *, tenant_id: str, role: str | None
    ) -> EffectiveGuardView:
        bot: Bot | None = await self._bot_repo.find_by_id(bot_id)
        if bot is None:
            raise EntityNotFoundError("Bot", bot_id)
        ensure_bot_tenant(bot, tenant_id, role)
        effective = await self._provider.effective_for(bot.tenant_id, bot)
        return EffectiveGuardView(
            tenant_id=bot.tenant_id, bot_id=bot.id.value,
            effective=effective, bot_stages=_bot_stages(bot),
        )
