"""異常控管設定三層（Issue #68 P7c）：平台預設 → 租戶覆寫 → （bot 覆寫，預留）

- 平台預設由程式常數 + 可選的 platform 列組成，system_admin 可改。
- 租戶只能在「平台允許範圍」內調；不開放租戶改：fail-open、回應不洩漏原因、稽核必寫、
  平台硬上限（門檻不可調到等於關閉）。
- 設定以 JSON 覆寫存放（只存有改的鍵），套用時合併到 AbusePolicy。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.domain.abuse.policy import AbuseMode, AbusePolicy, AbuseSignal, SubjectKind
from src.domain.shared.exceptions import ValidationError

SCOPE_PLATFORM = "platform"   # 系統預設（system_admin）
SCOPE_PROFILE = "profile"     # 方案（standard / strict / lenient …，system_admin）
SCOPE_TENANT = "tenant"       # 個別租戶：指定方案 + 微調（system_admin）
PLATFORM_SCOPE_ID = "*"
PROFILE_KEY = "profile"       # tenant overrides 內的特殊鍵：採用哪個方案
DEFAULT_PROFILE = "standard"

# 內建方案（可被 DB 的 profile 列覆寫或新增）
BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "standard": {},
    "strict": {
        "threshold_l1": 2, "threshold_l2": 5, "threshold_l3": 10, "threshold_l4": 20,
        "duration_l2": 600, "duration_l3": 1800, "duration_l4": 7200,
        "pacing_max_per_minute": 12,
    },
    "lenient": {
        "threshold_l1": 5, "threshold_l2": 12, "threshold_l3": 25, "threshold_l4": 50,
        "duration_l2": 180, "duration_l3": 600, "pacing_max_per_minute": 30,
    },
    "monitor": {"mode": "monitor"},
}

# 租戶可調的鍵與範圍（平台硬上限；門檻不可調到等於關閉）
BOUNDS: dict[str, tuple[float, float]] = {
    "decay_per_minute": (0.1, 10.0),
    "pacing_max_per_minute": (5, 120),
    "unrouted_free_count": (0, 10),
    "threshold_l1": (1, 50),
    "threshold_l2": (2, 100),
    "threshold_l3": (3, 200),
    "threshold_l4": (4, 400),
    "duration_l2": (60, 3600),
    "duration_l3": (300, 86400),
    "duration_l4": (3600, 86400),
    "slow_requests_per_minute": (1, 30),
}
BOOL_KEYS = frozenset({"enabled", "line_silent_on_cooldown", "ip_layer_enabled"})
WEIGHT_KEYS = frozenset(f"weight_{s.value}" for s in AbuseSignal)
MAX_LEVEL_KEYS = frozenset(f"max_level_{k.value}" for k in SubjectKind)
ALLOWED_KEYS = (
    set(BOUNDS) | BOOL_KEYS | WEIGHT_KEYS | MAX_LEVEL_KEYS
    | {"mode", "ip_allowlist", PROFILE_KEY}
)


@dataclass
class AbuseSettings:
    """一層覆寫（platform 或 tenant）。overrides 只含有改的鍵。"""

    scope_kind: str
    scope_id: str
    overrides: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    updated_by: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AbuseSettingsRepository(ABC):
    @abstractmethod
    async def get(self, scope_kind: str, scope_id: str) -> AbuseSettings | None: ...

    @abstractmethod
    async def save(self, settings: AbuseSettings) -> None: ...

    @abstractmethod
    async def list_profiles(self) -> list[AbuseSettings]: ...


def validate_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    """檢查鍵名與範圍；回傳正規化後的 dict。超出平台範圍 → ValidationError。"""
    unknown = sorted(set(overrides) - ALLOWED_KEYS)
    if unknown:
        raise ValidationError(f"Unknown abuse settings: {', '.join(unknown)}")
    clean = {key: _normalize(key, value) for key, value in overrides.items()}
    keys = [f"threshold_l{i}" for i in (1, 2, 3, 4)]
    known = [clean[k] for k in keys if k in clean]
    if known != sorted(known):
        raise ValidationError("thresholds must be increasing: L1 < L2 < L3 < L4")
    return clean


def _normalize(key: str, value: Any) -> Any:
    if key == PROFILE_KEY:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("profile must be a non-empty name")
        return value.strip()
    if key == "mode":
        if value not in (AbuseMode.MONITOR.value, AbuseMode.ENFORCE.value):
            raise ValidationError("mode must be monitor or enforce")
        return value
    if key in BOOL_KEYS:
        return bool(value)
    if key == "ip_allowlist":
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValidationError("ip_allowlist must be a list of strings")
        return [v.strip() for v in value if v.strip()]
    if key in WEIGHT_KEYS:
        _check_range(key, value, 0, 50)
        return float(value)
    if key in MAX_LEVEL_KEYS:
        _check_range(key, value, 0, 4)
        return int(value)
    lo, hi = BOUNDS[key]
    _check_range(key, value, lo, hi)
    return type(lo)(value)


def _check_range(key: str, value: Any, lo: float, hi: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValidationError(f"{key} must be a number")
    if not (lo <= value <= hi):
        raise ValidationError(f"{key} must be between {lo} and {hi}")


def apply_overrides(base: AbusePolicy, overrides: dict[str, Any]) -> AbusePolicy:
    """把一層覆寫合併進 policy（回新物件）。"""
    policy = replace(
        base,
        weights=dict(base.weights),
        thresholds=dict(base.thresholds),
        durations=dict(base.durations),
        max_level_by_kind=dict(base.max_level_by_kind),
    )
    for key, value in overrides.items():
        if key == PROFILE_KEY:
            continue
        if key == "mode":
            policy.mode = AbuseMode(value)
        elif key.startswith("threshold_l"):
            policy.thresholds[int(key[-1])] = float(value)
        elif key.startswith("duration_l"):
            policy.durations[int(key[-1])] = int(value)
        elif key.startswith("weight_"):
            policy.weights[AbuseSignal(key[len("weight_"):])] = float(value)
        elif key.startswith("max_level_"):
            policy.max_level_by_kind[SubjectKind(key[len("max_level_"):])] = int(value)
        elif key in ("enabled", "ip_allowlist", "ip_layer_enabled"):
            setattr(policy, key, value)
        else:
            setattr(policy, key, value)
    return policy


def resolve_policy(
    platform: AbuseSettings | None,
    tenant: AbuseSettings | None,
    profiles: dict[str, dict[str, Any]] | None = None,
) -> AbusePolicy:
    """預設 → 平台 → 方案（租戶指定，預設 standard）→ 租戶微調。"""
    all_profiles = dict(BUILTIN_PROFILES)
    all_profiles.update(profiles or {})
    policy = AbusePolicy()
    if platform is not None:
        policy = apply_overrides(policy, platform.overrides)
    profile_name = DEFAULT_PROFILE
    if tenant is not None and tenant.overrides.get(PROFILE_KEY):
        profile_name = str(tenant.overrides[PROFILE_KEY])
    policy = apply_overrides(policy, all_profiles.get(profile_name, {}))
    if tenant is not None:
        policy = apply_overrides(policy, tenant.overrides)
    return policy


def policy_view(policy: AbusePolicy) -> dict[str, Any]:
    """後台顯示用的攤平 dict（與 overrides 鍵名一致）。"""
    view: dict[str, Any] = {
        "mode": policy.mode.value,
        "enabled": policy.enabled,
        "decay_per_minute": policy.decay_per_minute,
        "pacing_max_per_minute": policy.pacing_max_per_minute,
        "unrouted_free_count": policy.unrouted_free_count,
        "slow_requests_per_minute": policy.slow_requests_per_minute,
        "line_silent_on_cooldown": policy.line_silent_on_cooldown,
        "ip_layer_enabled": policy.ip_layer_enabled,
        "ip_allowlist": list(policy.ip_allowlist),
    }
    for lvl in (1, 2, 3, 4):
        view[f"threshold_l{lvl}"] = policy.thresholds.get(lvl)
    for lvl in (2, 3, 4):
        view[f"duration_l{lvl}"] = policy.durations.get(lvl)
    for sig in AbuseSignal:
        view[f"weight_{sig.value}"] = policy.weights.get(sig, 0.0)
    for kind in SubjectKind:
        view[f"max_level_{kind.value}"] = policy.max_level_by_kind.get(kind)
    return view
