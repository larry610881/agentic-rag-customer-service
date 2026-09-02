"""設定指紋 snapshot / 時間軸 / diff API（Issue #60）"""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query

from src.application.observability.config_snapshot_use_cases import (
    DiffConfigSnapshotsUseCase,
    GetConfigSnapshotUseCase,
    GetConfigTimelineUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(prefix="/api/v1", tags=["config-snapshots"])


@router.get("/config-snapshots/diff")
@inject
async def diff_config_snapshots(
    a: str = Query(..., min_length=64, max_length=64),
    b: str = Query(..., min_length=64, max_length=64),
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: DiffConfigSnapshotsUseCase = Depends(
        Provide[Container.diff_config_snapshots_use_case]
    ),
) -> dict:
    try:
        return await use_case.execute(a, b)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.get("/config-snapshots/{config_hash}")
@inject
async def get_config_snapshot(
    config_hash: str,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: GetConfigSnapshotUseCase = Depends(
        Provide[Container.get_config_snapshot_use_case]
    ),
) -> dict:
    try:
        found = await use_case.execute(config_hash)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
    return {
        "hash": found["hash"],
        "schema": found["schema"],
        "first_seen_at": found["first_seen_at"].isoformat()
        if found.get("first_seen_at") else None,
        "snapshot": found["snapshot"],
    }


@router.get("/bots/{bot_id}/config-timeline")
@inject
async def get_bot_config_timeline(
    bot_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: GetConfigTimelineUseCase = Depends(
        Provide[Container.get_config_timeline_use_case]
    ),
) -> dict:
    items = await use_case.execute(bot_id, limit=limit)
    return {
        "bot_id": bot_id,
        "items": [
            {
                "hash": it["hash"],
                "first_seen_at": it["first_seen_at"].isoformat()
                if it.get("first_seen_at") else None,
                "last_seen_at": it["last_seen_at"].isoformat()
                if it.get("last_seen_at") else None,
                "turns": it["turns"],
            }
            for it in items
        ],
    }
