"""管理端變更稽核查詢 API（Issue #60）"""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src.application.audit.audit_recorder import ListAuditLogsUseCase
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, require_role

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])


@router.get("")
@inject
async def list_audit_logs(
    tenant_id: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: CurrentTenant = Depends(require_role("system_admin")),
    use_case: ListAuditLogsUseCase = Depends(
        Provide[Container.list_audit_logs_use_case]
    ),
) -> dict:
    entries = await use_case.execute(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "id": e.id,
                "tenant_id": e.tenant_id,
                "actor_user_id": e.actor_user_id,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "action": e.action,
                "changed_fields": e.changed_fields,
                "source": e.source,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
        "limit": limit,
        "offset": offset,
    }
