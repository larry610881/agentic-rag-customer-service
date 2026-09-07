"""防護階段三層設定（Issue #75）

防護階段像 worker 一樣可勾選：系統層管「底線（required）」與預設、方案層給不同預設、
租戶層與 bot 層只能在底線之上**加**階段，不能減；系統管理員可鎖定特定租戶（鎖定時忽略
租戶與 bot 的覆寫）。解析結果 EffectiveGuard 由三通路共用的 guard_pipeline 讀取。

| stage              | 對應 | 成本 |
|--------------------|------|------|
| regex_input        | PromptGuardService.check_input | 0 |
| classifier_attack  | 分類器 is_attack；kb 模式不帶 worker 只做攻擊判定 | 1 次小模型 |
| output_guard       | PromptGuardService.check_output | 0 |
| abuse_scoring      | P7 record / evaluate | 0（Redis） |
| local_classifier   | 預留（地端小模型），目前解析為 no-op | — |
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from src.domain.settings.layered import (
    DEFAULT_PROFILE,
    PLATFORM_SCOPE_ID,
    PROFILE_KEY,
    SCOPE_KINDS,
    SCOPE_PLATFORM,
    SCOPE_PROFILE,
    SCOPE_TENANT,
    LayeredSettings,
    LayeredSettingsRepository,
    resolve_layers,
    validate_profile_name,
)
from src.domain.shared.exceptions import ValidationError

__all__ = [
    "DEFAULT_PROFILE",
    "PLATFORM_SCOPE_ID",
    "PROFILE_KEY",
    "SCOPE_PLATFORM",
    "SCOPE_PROFILE",
    "SCOPE_TENANT",
    "STAGES",
    "REQUIRED_FLOOR_DEFAULT",
    "PLATFORM_DEFAULT_STAGES",
    "BUILTIN_PROFILES",
    "GuardSettings",
    "GuardSettingsRepository",
    "EffectiveGuard",
    "ALL_STAGES_ON",
    "resolve_guard",
    "validate_guard_overrides",
    "validate_bot_guard_stages",
]

STAGE_REGEX_INPUT = "regex_input"
STAGE_CLASSIFIER_ATTACK = "classifier_attack"
STAGE_OUTPUT_GUARD = "output_guard"
STAGE_ABUSE_SCORING = "abuse_scoring"
STAGE_LOCAL_CLASSIFIER = "local_classifier"  # 預留：解析為 no-op

STAGES: tuple[str, ...] = (
    STAGE_REGEX_INPUT,
    STAGE_CLASSIFIER_ATTACK,
    STAGE_OUTPUT_GUARD,
    STAGE_ABUSE_SCORING,
    STAGE_LOCAL_CLASSIFIER,
)
_STAGE_ORDER = {name: i for i, name in enumerate(STAGES)}

# Q7（Larry 09-07 預設）：底線 = regex + output + abuse 必開；
# classifier_attack 平台預設開（展覽方案關）
REQUIRED_FLOOR_DEFAULT: tuple[str, ...] = (
    STAGE_REGEX_INPUT, STAGE_OUTPUT_GUARD, STAGE_ABUSE_SCORING,
)
PLATFORM_DEFAULT_STAGES: tuple[str, ...] = (
    STAGE_REGEX_INPUT, STAGE_CLASSIFIER_ATTACK, STAGE_OUTPUT_GUARD, STAGE_ABUSE_SCORING,
)

KEY_STAGES = "stages"                    # 各層：啟用清單
KEY_REQUIRED = "required_stages"         # 僅 platform：底線
KEY_LOCKED = "locked"                    # 僅 tenant：鎖定（system_admin 寫）
ALLOWED_KEYS_BY_SCOPE: dict[str, frozenset[str]] = {
    SCOPE_PLATFORM: frozenset({KEY_STAGES, KEY_REQUIRED}),
    SCOPE_PROFILE: frozenset({KEY_STAGES}),
    SCOPE_TENANT: frozenset({KEY_STAGES, KEY_LOCKED, PROFILE_KEY}),
}

# 內建方案：standard = 沿用平台預設；exhibition = 展覽用（省掉分類器那次小模型）
BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "standard": {},
    "exhibition": {
        KEY_STAGES: [STAGE_REGEX_INPUT, STAGE_OUTPUT_GUARD, STAGE_ABUSE_SCORING],
    },
}

SOURCE_REQUIRED = "required"
SOURCE_PLATFORM = "platform"
SOURCE_PROFILE = "profile"
SOURCE_TENANT = "tenant"
SOURCE_BOT = "bot"
SOURCE_FALLBACK = "fallback"


@dataclass
class GuardSettings(LayeredSettings):
    """一層防護覆寫（platform / profile / tenant）。"""


class GuardSettingsRepository(LayeredSettingsRepository):
    @abstractmethod
    async def get(self, scope_kind: str, scope_id: str) -> GuardSettings | None: ...

    @abstractmethod
    async def save(self, settings: GuardSettings) -> None: ...

    @abstractmethod
    async def list_profiles(self) -> list[GuardSettings]: ...


def _ordered(stages: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(stages), key=lambda s: _STAGE_ORDER[s]))


def normalize_stage_list(value: Any, key: str = KEY_STAGES) -> list[str]:
    """階段清單：必須是字串 list，且每個名稱都在 STAGES；去重、依固定順序。"""
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValidationError(f"{key} must be a list of stage names")
    unknown = sorted(set(value) - set(STAGES))
    if unknown:
        raise ValidationError(f"Unknown guard stage: {', '.join(unknown)}")
    return list(_ordered(value))


def validate_guard_overrides(
    overrides: Mapping[str, Any], scope_kind: str
) -> dict[str, Any]:
    """檢查鍵名、階段名稱與該層允許的鍵；回傳正規化後的 dict。"""
    if scope_kind not in SCOPE_KINDS:
        raise ValidationError("scope_kind must be platform, profile or tenant")
    allowed = ALLOWED_KEYS_BY_SCOPE[scope_kind]
    unknown = sorted(set(overrides) - allowed)
    if unknown:
        raise ValidationError(
            f"Unknown guard settings for {scope_kind}: {', '.join(unknown)}"
        )
    clean: dict[str, Any] = {}
    for key, value in overrides.items():
        if key in (KEY_STAGES, KEY_REQUIRED):
            clean[key] = normalize_stage_list(value, key)
        elif key == KEY_LOCKED:
            clean[key] = bool(value)
        elif key == PROFILE_KEY:
            clean[key] = validate_profile_name(value)
    return clean


@dataclass(frozen=True)
class EffectiveGuard:
    """解析後的有效防護：階段清單、底線、鎖定、各階段來源。"""

    stages: tuple[str, ...]
    required: tuple[str, ...]
    locked: bool = False
    source_map: dict[str, str] | None = None
    profile: str = DEFAULT_PROFILE

    def enabled(self, stage: str) -> bool:
        return stage in self.stages

    @property
    def sources(self) -> dict[str, str]:
        return dict(self.source_map or {})

    def with_bot(self, bot_stages: Iterable[str] | None) -> EffectiveGuard:
        """bot 只能加不能減；鎖定時忽略 bot 覆寫。未知階段 → ValidationError。"""
        if bot_stages is None or self.locked:
            return self
        extra = [
            s for s in normalize_stage_list(list(bot_stages)) if s not in self.stages
        ]
        if not extra:
            return self
        sources = self.sources
        sources.update(dict.fromkeys(extra, SOURCE_BOT))
        return EffectiveGuard(
            stages=_ordered((*self.stages, *extra)),
            required=self.required,
            locked=self.locked,
            source_map=sources,
            profile=self.profile,
        )

    def view(self) -> dict[str, Any]:
        return {
            "stages": list(self.stages),
            "required": list(self.required),
            "locked": self.locked,
            "source_map": self.sources,
            "profile": self.profile,
        }


# DB 失效時的 fail-safe：防護寧多勿少 → 全部階段開啟
ALL_STAGES_ON = EffectiveGuard(
    stages=STAGES,
    required=REQUIRED_FLOOR_DEFAULT,
    locked=False,
    source_map=dict.fromkeys(STAGES, SOURCE_FALLBACK),
)


def resolve_guard(
    platform: LayeredSettings | None,
    tenant: LayeredSettings | None,
    profiles: Mapping[str, dict[str, Any]] | None = None,
    bot_stages: Iterable[str] | None = None,
) -> EffectiveGuard:
    """底線 ∪ 方案預設（無方案覆寫時為平台預設）∪ 租戶加嚴 ∪ bot 加嚴。

    - 結果一定 ⊇ required（platform.required_stages，未設時為 REQUIRED_FLOOR_DEFAULT）
    - 方案給的是「預設集合」（可少於平台預設，但不能少於底線——底線由聯集保證）
    - 租戶 / bot 只能加；鎖定時忽略租戶與 bot 覆寫
    - 任一層出現未知階段 → ValidationError
    """
    layers = resolve_layers(
        platform, tenant, profiles, builtin_profiles=BUILTIN_PROFILES,
    )
    required = (
        normalize_stage_list(layers.platform[KEY_REQUIRED], KEY_REQUIRED)
        if KEY_REQUIRED in layers.platform
        else list(REQUIRED_FLOOR_DEFAULT)
    )
    platform_stages = (
        normalize_stage_list(layers.platform[KEY_STAGES])
        if KEY_STAGES in layers.platform
        else list(PLATFORM_DEFAULT_STAGES)
    )
    if KEY_STAGES in layers.profile:
        base_stages = normalize_stage_list(layers.profile[KEY_STAGES])
        base_source = SOURCE_PROFILE
    else:
        base_stages = platform_stages
        base_source = SOURCE_PLATFORM

    sources: dict[str, str] = {}
    for s in required:
        sources.setdefault(s, SOURCE_REQUIRED)
    for s in base_stages:
        sources.setdefault(s, base_source)

    locked = bool(layers.tenant.get(KEY_LOCKED, False))
    if not locked and KEY_STAGES in layers.tenant:
        for s in normalize_stage_list(layers.tenant[KEY_STAGES]):
            sources.setdefault(s, SOURCE_TENANT)

    effective = EffectiveGuard(
        stages=_ordered(sources),
        required=_ordered(required),
        locked=locked,
        source_map=sources,
        profile=layers.profile_name,
    )
    return effective.with_bot(bot_stages)


def validate_bot_guard_stages(
    stages: Iterable[str] | None, effective: EffectiveGuard
) -> list[str] | None:
    """bot 儲存時的超集規則：None = 繼承；否則必須 ⊇ 租戶有效集合；鎖定時不得自設。"""
    if stages is None:
        return None
    clean = normalize_stage_list(list(stages))
    if effective.locked:
        raise ValidationError(
            "guard_stages are locked by the platform for this tenant"
        )
    missing = [s for s in effective.stages if s not in clean]
    if missing:
        raise ValidationError(
            "guard_stages cannot remove tenant-effective stages: "
            + ", ".join(missing)
        )
    return clean
