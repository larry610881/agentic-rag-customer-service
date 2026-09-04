"""Widget 宿主身分綁定 — 租戶 secret 管理（Issue #68 P7b）

tenant_admin 管自己租戶；system_admin 可帶 ?tenant_id= 跨租戶。
secret 只在輪替時回傳一次。
"""

from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.application.widget.identity_use_cases import (
    GetIdentitySecretStatusUseCase,
    RotateIdentitySecretUseCase,
    UpdateIdentityPolicyUseCase,
)
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, require_role

router = APIRouter(prefix="/api/v1/widget-identity", tags=["widget-identity"])

_MANAGERS = require_role("tenant_admin", "system_admin")


class UpdatePolicyBody(BaseModel):
    is_enabled: bool | None = None
    enforce_verified: bool | None = None


def _target_tenant(caller: CurrentTenant, requested: str | None) -> str:
    if caller.role == "system_admin":
        if not requested:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="system_admin must specify tenant_id",
            )
        return requested
    if requested and requested != caller.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return caller.tenant_id


def _status_dict(s: Any) -> dict[str, Any]:
    return {
        "tenant_id": s.tenant_id,
        "has_secret": s.has_secret,
        "is_enabled": s.is_enabled,
        "enforce_verified": s.enforce_verified,
        "rotated_at": s.rotated_at.isoformat() if s.rotated_at else None,
    }


@router.get("/secret")
@inject
async def get_status(
    tenant_id: str | None = Query(default=None),
    caller: CurrentTenant = Depends(_MANAGERS),
    use_case: GetIdentitySecretStatusUseCase = Depends(
        Provide[Container.get_identity_secret_status_use_case]
    ),
) -> dict[str, Any]:
    return _status_dict(await use_case.execute(_target_tenant(caller, tenant_id)))


@router.post("/secret/rotate")
@inject
async def rotate_secret(
    tenant_id: str | None = Query(default=None),
    caller: CurrentTenant = Depends(_MANAGERS),
    use_case: RotateIdentitySecretUseCase = Depends(
        Provide[Container.rotate_identity_secret_use_case]
    ),
) -> dict[str, Any]:
    target = _target_tenant(caller, tenant_id)
    secret = await use_case.execute(target, actor_user_id=caller.user_id)
    return {"tenant_id": target, "secret": secret}  # 只回這一次


@router.put("/secret")
@inject
async def update_policy(
    body: UpdatePolicyBody,
    tenant_id: str | None = Query(default=None),
    caller: CurrentTenant = Depends(_MANAGERS),
    use_case: UpdateIdentityPolicyUseCase = Depends(
        Provide[Container.update_identity_policy_use_case]
    ),
) -> dict[str, Any]:
    target = _target_tenant(caller, tenant_id)
    result = await use_case.execute(
        target, is_enabled=body.is_enabled, enforce_verified=body.enforce_verified,
        actor_user_id=caller.user_id,
    )
    return _status_dict(result)
