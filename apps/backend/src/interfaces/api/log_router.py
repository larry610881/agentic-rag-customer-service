"""Request log viewer API — direct DB queries (no DDD layer)."""

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.models.request_log_model import RequestLogModel

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


@router.get("")
async def list_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    path: str | None = Query(default=None),
    min_elapsed_ms: float | None = Query(default=None, ge=0),
):
    """Paginated request log listing with optional filters."""
    async with async_session_factory() as session:
        stmt = select(RequestLogModel).order_by(
            RequestLogModel.created_at.desc()
        )

        count_stmt = select(func.count()).select_from(RequestLogModel)

        if path:
            stmt = stmt.where(RequestLogModel.path.contains(path))
            count_stmt = count_stmt.where(RequestLogModel.path.contains(path))
        if min_elapsed_ms is not None:
            stmt = stmt.where(RequestLogModel.elapsed_ms >= min_elapsed_ms)
            count_stmt = count_stmt.where(
                RequestLogModel.elapsed_ms >= min_elapsed_ms
            )

        total = (await session.execute(count_stmt)).scalar() or 0
        rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "request_id": r.request_id,
                "method": r.method,
                "path": r.path,
                "status_code": r.status_code,
                "elapsed_ms": r.elapsed_ms,
                "trace_steps": r.trace_steps,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/{request_id}")
async def get_log_detail(request_id: str):
    """Single request log by request_id."""
    async with async_session_factory() as session:
        stmt = select(RequestLogModel).where(
            RequestLogModel.request_id == request_id
        )
        row = (await session.execute(stmt)).scalar_one_or_none()

    if row is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Log not found")

    return {
        "id": row.id,
        "request_id": row.request_id,
        "method": row.method,
        "path": row.path,
        "status_code": row.status_code,
        "elapsed_ms": row.elapsed_ms,
        "trace_steps": row.trace_steps,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
