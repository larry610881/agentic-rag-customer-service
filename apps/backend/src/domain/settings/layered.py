"""分層設定共用機制（Issue #75，自 #68 abuse_settings 抽出）

平台（system_admin 的系統預設）→ 方案（profile，system_admin 維護）→ 租戶（指定方案 +
微調）三層覆寫。每層只存「有改的鍵」，各功能（異常控管、防護階段…）自帶鍵表、驗證與
合併規則；本模組只管 scope / 方案挑選 / 三層攤開，不知道鍵的語意。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.domain.shared.exceptions import ValidationError

SCOPE_PLATFORM = "platform"   # 系統預設（system_admin）
SCOPE_PROFILE = "profile"     # 方案（system_admin）
SCOPE_TENANT = "tenant"       # 個別租戶：指定方案 + 微調（system_admin）
SCOPE_KINDS = (SCOPE_PLATFORM, SCOPE_PROFILE, SCOPE_TENANT)
PLATFORM_SCOPE_ID = "*"
PROFILE_KEY = "profile"       # tenant overrides 內的特殊鍵：採用哪個方案
DEFAULT_PROFILE = "standard"


@dataclass
class LayeredSettings:
    """一層覆寫（platform / profile / tenant）。overrides 只含有改的鍵。"""

    scope_kind: str
    scope_id: str
    overrides: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    updated_by: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LayeredSettingsRepository(ABC):
    @abstractmethod
    async def get(self, scope_kind: str, scope_id: str) -> Any | None: ...

    @abstractmethod
    async def save(self, settings: Any) -> None: ...

    @abstractmethod
    async def list_profiles(self) -> list[Any]: ...


def validate_scope_kind(scope_kind: str) -> None:
    if scope_kind not in SCOPE_KINDS:
        raise ValidationError("scope_kind must be platform, profile or tenant")


def normalize_scope_id(scope_kind: str, scope_id: str) -> str:
    """platform 只有一列（scope_id 固定 "*"）；其他層沿用呼叫端給的 id。"""
    if scope_kind == SCOPE_PLATFORM:
        return PLATFORM_SCOPE_ID
    scope_id = (scope_id or "").strip()
    if not scope_id:
        raise ValidationError("scope_id is required")
    return scope_id


def validate_profile_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("profile must be a non-empty name")
    return value.strip()


def profile_name_of(
    tenant: LayeredSettings | None, default: str = DEFAULT_PROFILE
) -> str:
    """租戶指定的方案名；未指定 → default。"""
    if tenant is not None and tenant.overrides.get(PROFILE_KEY):
        return str(tenant.overrides[PROFILE_KEY])
    return default


def merge_profiles(
    builtin: Mapping[str, dict[str, Any]],
    stored: Iterable[LayeredSettings] | Mapping[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """內建方案 + DB 方案列（同名以 DB 為準）。"""
    merged: dict[str, dict[str, Any]] = {k: dict(v) for k, v in builtin.items()}
    if stored is None:
        return merged
    if isinstance(stored, Mapping):
        merged.update({k: dict(v) for k, v in stored.items()})
    else:
        merged.update({p.scope_id: dict(p.overrides) for p in stored})
    return merged


@dataclass(frozen=True)
class ResolvedLayers:
    """三層攤開後的覆寫 dict（呼叫端依自身語意合併）。"""

    platform: dict[str, Any]
    profile_name: str
    profile: dict[str, Any]
    tenant: dict[str, Any]


def resolve_layers(
    platform: LayeredSettings | None,
    tenant: LayeredSettings | None,
    profiles: Mapping[str, dict[str, Any]] | None,
    *,
    builtin_profiles: Mapping[str, dict[str, Any]],
    default_profile: str = DEFAULT_PROFILE,
) -> ResolvedLayers:
    """平台 → 方案（租戶指定，預設 default_profile；未知方案視同空）→ 租戶。"""
    all_profiles = merge_profiles(builtin_profiles, profiles)
    name = profile_name_of(tenant, default_profile)
    return ResolvedLayers(
        platform=dict(platform.overrides) if platform is not None else {},
        profile_name=name,
        profile=dict(all_profiles.get(name, {})),
        tenant=dict(tenant.overrides) if tenant is not None else {},
    )
