"""防護階段設定 API（Issue #75）

- `/api/v1/admin/guard/settings/*`：platform / profile / tenant 三層，
  **寫入僅 system_admin**；tenant_admin 只能讀自己租戶的生效設定。
- `/api/v1/guard/effective?bot_id=`：租戶端讀某 bot 的有效防護
  （階段 / 底線 / 鎖定 / 來源），歸屬檢查與 GetBot 一致（跨租戶 → 404）。
"""

from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.application.security.guard_settings_use_cases import (
    GetEffectiveGuardUseCase,
    GetGuardOverviewUseCase,
    GetTenantGuardUseCase,
    UpdateGuardSettingsUseCase,
)
from src.container import Container
from src.domain.security.guard_stages import (
    ALLOWED_KEYS_BY_SCOPE,
    BUILTIN_PROFILES,
    REQUIRED_FLOOR_DEFAULT,
    SCOPE_PLATFORM,
    SCOPE_PROFILE,
    SCOPE_TENANT,
    STAGES,
)
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError
from src.interfaces.api.deps import CurrentTenant, require_role

router = APIRouter(tags=["guard-stages"])

_ADMIN_PREFIX = "/api/v1/admin/guard/settings"
_SYSTEM = require_role("system_admin")
_MANAGERS = require_role("tenant_admin", "system_admin")


class OverridesBody(BaseModel):
    overrides: dict[str, Any] = {}


class TenantGuardBody(BaseModel):
    profile: str | None = None
    overrides: dict[str, Any] = {}
    locked: bool | None = None


def _own_or_admin_tenant(caller: CurrentTenant, tenant_id: str) -> str:
    if caller.role == "system_admin":
        return tenant_id
    if tenant_id != caller.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return tenant_id


@router.get(_ADMIN_PREFIX)
@inject
async def get_guard_overview(
    _caller: CurrentTenant = Depends(_SYSTEM),
    use_case: GetGuardOverviewUseCase = Depends(
        Provide[Container.get_guard_overview_use_case]
    ),
) -> dict[str, Any]:
    overview = await use_case.execute()
    return {
        "platform_overrides": overview.platform_overrides,
        "profiles": overview.profiles,
        "effective_default": overview.effective_default.view(),
        "stages": list(STAGES),
        "required_floor_default": list(REQUIRED_FLOOR_DEFAULT),
        "builtin_profiles": sorted(BUILTIN_PROFILES),
        "allowed_keys": {k: sorted(v) for k, v in ALLOWED_KEYS_BY_SCOPE.items()},
    }


@router.put(f"{_ADMIN_PREFIX}/platform")
@inject
async def update_platform_guard(
    body: OverridesBody,
    caller: CurrentTenant = Depends(_SYSTEM),
    use_case: UpdateGuardSettingsUseCase = Depends(
        Provide[Container.update_guard_settings_use_case]
    ),
) -> dict[str, Any]:
    return await _update(use_case, SCOPE_PLATFORM, "*", body.overrides, caller)


@router.put(f"{_ADMIN_PREFIX}/profiles/{{name}}")
@inject
async def update_guard_profile(
    name: str,
    body: OverridesBody,
    caller: CurrentTenant = Depends(_SYSTEM),
    use_case: UpdateGuardSettingsUseCase = Depends(
        Provide[Container.update_guard_settings_use_case]
    ),
) -> dict[str, Any]:
    return await _update(use_case, SCOPE_PROFILE, name.strip(), body.overrides, caller)


@router.get(f"{_ADMIN_PREFIX}/tenants/{{tenant_id}}")
@inject
async def get_tenant_guard(
    tenant_id: str,
    caller: CurrentTenant = Depends(_MANAGERS),
    use_case: GetTenantGuardUseCase = Depends(
        Provide[Container.get_tenant_guard_use_case]
    ),
) -> dict[str, Any]:
    tenant_id = _own_or_admin_tenant(caller, tenant_id)
    result = await use_case.execute(tenant_id)
    return {
        "tenant_id": result.tenant_id,
        "profile": result.profile,
        "overrides": result.overrides,
        "locked": result.locked,
        "effective": result.effective.view(),
        "editable": caller.role == "system_admin",
    }


@router.put(f"{_ADMIN_PREFIX}/tenants/{{tenant_id}}")
@inject
async def update_tenant_guard(
    tenant_id: str,
    body: TenantGuardBody,
    caller: CurrentTenant = Depends(_SYSTEM),
    use_case: UpdateGuardSettingsUseCase = Depends(
        Provide[Container.update_guard_settings_use_case]
    ),
) -> dict[str, Any]:
    return await _update(
        use_case, SCOPE_TENANT, tenant_id, body.overrides, caller,
        profile=body.profile, locked=body.locked,
    )


async def _update(
    use_case: UpdateGuardSettingsUseCase,
    scope_kind: str,
    scope_id: str,
    overrides: dict[str, Any],
    caller: CurrentTenant,
    profile: str | None = None,
    locked: bool | None = None,
) -> dict[str, Any]:
    try:
        saved = await use_case.execute(
            scope_kind=scope_kind, scope_id=scope_id, overrides=overrides,
            actor_user_id=caller.user_id, actor_role=caller.role,
            profile=profile, locked=locked,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message
        ) from None
    return {
        "scope_kind": saved.scope_kind,
        "scope_id": saved.scope_id,
        "overrides": saved.overrides,
        "updated_at": saved.updated_at.isoformat(),
    }


@router.get("/api/v1/guard/effective")
@inject
async def get_effective_guard(
    bot_id: str = Query(..., min_length=1, max_length=64),
    caller: CurrentTenant = Depends(_MANAGERS),
    use_case: GetEffectiveGuardUseCase = Depends(
        Provide[Container.get_effective_guard_use_case]
    ),
) -> dict[str, Any]:
    """租戶端：某 bot 的有效防護階段（含底線 / 鎖定 / 各階段來源 / bot 自設值）。"""
    try:
        view = await use_case.execute(
            bot_id, tenant_id=caller.tenant_id, role=caller.role
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from None
    return view.to_dict()
