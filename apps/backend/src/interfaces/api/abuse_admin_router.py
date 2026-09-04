"""異常控管後台 API（Issue #68 P7c）

- 設定（platform / profile / tenant）：**寫入僅 system_admin**；tenant_admin 只能讀自己
  租戶的生效設定。
- 受控清單：system_admin 全部或指定租戶；tenant_admin 自己租戶（只讀）。
- 解除：僅 system_admin（寫稽核）。
"""

from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.application.abuse.abuse_settings_use_cases import (
    GetAbuseSettingsOverviewUseCase,
    GetTenantAbuseSettingsUseCase,
    ListAbuseControlsUseCase,
    ReleaseAbuseControlUseCase,
    UpdateAbuseSettingsUseCase,
)
from src.container import Container
from src.domain.abuse.settings import (
    ALLOWED_KEYS,
    BOUNDS,
    SCOPE_PLATFORM,
    SCOPE_PROFILE,
    SCOPE_TENANT,
)
from src.domain.shared.exceptions import ValidationError
from src.interfaces.api.deps import CurrentTenant, require_role

router = APIRouter(prefix="/api/v1/admin/abuse", tags=["abuse-control"])

_SYSTEM = require_role("system_admin")
_MANAGERS = require_role("tenant_admin", "system_admin")


class OverridesBody(BaseModel):
    overrides: dict[str, Any] = {}


class TenantSettingsBody(BaseModel):
    profile: str | None = None
    overrides: dict[str, Any] = {}


class ReleaseBody(BaseModel):
    tenant_id: str | None = None
    subject_kind: str
    subject_id: str


def _own_or_admin_tenant(caller: CurrentTenant, tenant_id: str) -> str:
    if caller.role == "system_admin":
        return tenant_id
    if tenant_id != caller.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return tenant_id


@router.get("/settings")
@inject
async def get_settings_overview(
    _caller: CurrentTenant = Depends(_SYSTEM),
    use_case: GetAbuseSettingsOverviewUseCase = Depends(
        Provide[Container.get_abuse_settings_overview_use_case]
    ),
) -> dict[str, Any]:
    overview = await use_case.execute()
    return {
        "platform_overrides": overview.platform_overrides,
        "profiles": overview.profiles,
        "effective_default": overview.effective_default,
        "allowed_keys": sorted(ALLOWED_KEYS),
        "bounds": {k: list(v) for k, v in BOUNDS.items()},
    }


@router.put("/settings/platform")
@inject
async def update_platform_settings(
    body: OverridesBody,
    caller: CurrentTenant = Depends(_SYSTEM),
    use_case: UpdateAbuseSettingsUseCase = Depends(
        Provide[Container.update_abuse_settings_use_case]
    ),
) -> dict[str, Any]:
    return await _update(use_case, SCOPE_PLATFORM, "*", body.overrides, caller)


@router.put("/settings/profiles/{name}")
@inject
async def update_profile(
    name: str,
    body: OverridesBody,
    caller: CurrentTenant = Depends(_SYSTEM),
    use_case: UpdateAbuseSettingsUseCase = Depends(
        Provide[Container.update_abuse_settings_use_case]
    ),
) -> dict[str, Any]:
    return await _update(use_case, SCOPE_PROFILE, name.strip(), body.overrides, caller)


@router.get("/settings/tenants/{tenant_id}")
@inject
async def get_tenant_settings(
    tenant_id: str,
    caller: CurrentTenant = Depends(_MANAGERS),
    use_case: GetTenantAbuseSettingsUseCase = Depends(
        Provide[Container.get_tenant_abuse_settings_use_case]
    ),
) -> dict[str, Any]:
    tenant_id = _own_or_admin_tenant(caller, tenant_id)
    result = await use_case.execute(tenant_id)
    return {
        "tenant_id": result.tenant_id,
        "profile": result.profile,
        "overrides": result.overrides,
        "effective": result.effective,
        "editable": caller.role == "system_admin",
    }


@router.put("/settings/tenants/{tenant_id}")
@inject
async def update_tenant_settings(
    tenant_id: str,
    body: TenantSettingsBody,
    caller: CurrentTenant = Depends(_SYSTEM),
    use_case: UpdateAbuseSettingsUseCase = Depends(
        Provide[Container.update_abuse_settings_use_case]
    ),
) -> dict[str, Any]:
    return await _update(
        use_case, SCOPE_TENANT, tenant_id, body.overrides, caller, profile=body.profile
    )


async def _update(
    use_case: UpdateAbuseSettingsUseCase,
    scope_kind: str,
    scope_id: str,
    overrides: dict[str, Any],
    caller: CurrentTenant,
    profile: str | None = None,
) -> dict[str, Any]:
    try:
        saved = await use_case.execute(
            scope_kind=scope_kind, scope_id=scope_id, overrides=overrides,
            actor_user_id=caller.user_id, profile=profile,
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


@router.get("/controls")
@inject
async def list_controls(
    tenant_id: str | None = Query(default=None),
    caller: CurrentTenant = Depends(_MANAGERS),
    use_case: ListAbuseControlsUseCase = Depends(
        Provide[Container.list_abuse_controls_use_case]
    ),
) -> list[dict[str, Any]]:
    if caller.role != "system_admin":
        tenant_id = caller.tenant_id  # 租戶管理員只看自己
    rows = await use_case.execute(tenant_id)
    return [
        {
            "tenant_id": r.tenant_id,
            "subject_kind": r.subject_kind,
            "subject_id": r.subject_id if caller.role == "system_admin" else None,
            "subject_masked": r.subject_masked,
            "level": r.level,
            "remaining_seconds": r.remaining_seconds,
        }
        for r in rows
    ]


@router.post("/controls/release", status_code=204)
@inject
async def release_control(
    body: ReleaseBody,
    caller: CurrentTenant = Depends(_SYSTEM),
    use_case: ReleaseAbuseControlUseCase = Depends(
        Provide[Container.release_abuse_control_use_case]
    ),
) -> None:
    if not body.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tenant_id is required",
        )
    try:
        await use_case.execute(
            tenant_id=body.tenant_id, subject_kind=body.subject_kind,
            subject_id=body.subject_id, actor_user_id=caller.user_id,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown subject_kind",
        ) from None
