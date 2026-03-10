"""Observability API — RAG trace & evaluation viewer (direct DB queries)."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.models.bot_model import BotModel
from src.infrastructure.db.models.conversation_model import ConversationModel
from src.infrastructure.db.models.message_model import MessageModel
from src.infrastructure.db.models.rag_eval_model import RAGEvalModel
from src.infrastructure.db.models.rag_trace_model import RAGTraceModel
from src.infrastructure.db.models.tenant_model import TenantModel
from src.infrastructure.db.models.usage_record_model import UsageRecordModel

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])


@router.get("/traces")
async def list_traces(
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
):
    async with async_session_factory() as session:
        stmt = select(RAGTraceModel).order_by(RAGTraceModel.created_at.desc())
        count_stmt = select(func.count()).select_from(RAGTraceModel)

        if tenant_id:
            stmt = stmt.where(RAGTraceModel.tenant_id == tenant_id)
            count_stmt = count_stmt.where(RAGTraceModel.tenant_id == tenant_id)
        if date_from:
            stmt = stmt.where(RAGTraceModel.created_at >= date_from)
            count_stmt = count_stmt.where(RAGTraceModel.created_at >= date_from)
        if date_to:
            stmt = stmt.where(RAGTraceModel.created_at <= date_to)
            count_stmt = count_stmt.where(RAGTraceModel.created_at <= date_to)

        total = (await session.execute(count_stmt)).scalar() or 0
        rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "trace_id": r.trace_id,
                "query": r.query,
                "tenant_id": r.tenant_id,
                "message_id": r.message_id,
                "steps": r.steps,
                "total_ms": r.total_ms,
                "chunk_count": r.chunk_count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/evaluations")
async def list_evaluations(
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant_id: str | None = Query(default=None),
    layer: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=1),
):
    async with async_session_factory() as session:
        stmt = select(RAGEvalModel).order_by(RAGEvalModel.created_at.desc())
        count_stmt = select(func.count()).select_from(RAGEvalModel)

        if tenant_id:
            stmt = stmt.where(RAGEvalModel.tenant_id == tenant_id)
            count_stmt = count_stmt.where(RAGEvalModel.tenant_id == tenant_id)
        if layer:
            stmt = stmt.where(RAGEvalModel.layer == layer)
            count_stmt = count_stmt.where(RAGEvalModel.layer == layer)
        if min_score is not None:
            stmt = stmt.where(RAGEvalModel.avg_score >= min_score)
            count_stmt = count_stmt.where(RAGEvalModel.avg_score >= min_score)

        total = (await session.execute(count_stmt)).scalar() or 0
        rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "eval_id": r.eval_id,
                "message_id": r.message_id,
                "trace_id": r.trace_id,
                "tenant_id": r.tenant_id,
                "layer": r.layer,
                "dimensions": r.dimensions,
                "avg_score": r.avg_score,
                "model_used": r.model_used,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/token-usage")
async def get_token_usage(
    days: int = Query(default=30, ge=1, le=365),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session_factory() as session:
        stmt = (
            select(
                UsageRecordModel.tenant_id,
                TenantModel.name.label("tenant_name"),
                ConversationModel.bot_id,
                BotModel.name.label("bot_name"),
                UsageRecordModel.model,
                func.sum(UsageRecordModel.input_tokens).label("input_tokens"),
                func.sum(UsageRecordModel.output_tokens).label("output_tokens"),
                func.sum(UsageRecordModel.total_tokens).label("total_tokens"),
                func.sum(UsageRecordModel.estimated_cost).label("estimated_cost"),
                func.count().label("message_count"),
            )
            .outerjoin(
                MessageModel,
                UsageRecordModel.message_id == MessageModel.id,
            )
            .outerjoin(
                ConversationModel,
                MessageModel.conversation_id == ConversationModel.id,
            )
            .outerjoin(
                BotModel,
                ConversationModel.bot_id == BotModel.id,
            )
            .outerjoin(
                TenantModel,
                UsageRecordModel.tenant_id == TenantModel.id,
            )
            .where(UsageRecordModel.created_at >= since)
            .group_by(
                UsageRecordModel.tenant_id,
                TenantModel.name,
                ConversationModel.bot_id,
                BotModel.name,
                UsageRecordModel.model,
            )
            .order_by(func.sum(UsageRecordModel.estimated_cost).desc())
        )

        rows = (await session.execute(stmt)).all()

    return {
        "items": [
            {
                "tenant_id": r.tenant_id,
                "tenant_name": r.tenant_name or "(未知租戶)",
                "bot_id": r.bot_id,
                "bot_name": r.bot_name or "(未指定 Bot)",
                "model": r.model,
                "input_tokens": r.input_tokens or 0,
                "output_tokens": r.output_tokens or 0,
                "total_tokens": r.total_tokens or 0,
                "estimated_cost": float(r.estimated_cost or 0),
                "message_count": r.message_count or 0,
            }
            for r in rows
        ],
    }
