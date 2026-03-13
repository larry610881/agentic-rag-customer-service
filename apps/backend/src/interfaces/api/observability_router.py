"""Observability API — RAG trace & evaluation viewer (direct DB queries)."""

from datetime import datetime, timedelta, timezone

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from src.application.observability.diagnostic_rules_use_cases import (
    GetDiagnosticRulesUseCase,
    ResetDiagnosticRulesUseCase,
    UpdateDiagnosticRulesCommand,
    UpdateDiagnosticRulesUseCase,
)
from src.application.observability.log_retention_use_cases import (
    ExecuteLogCleanupUseCase,
    GetLogRetentionPolicyUseCase,
    UpdateLogRetentionPolicyCommand,
    UpdateLogRetentionPolicyUseCase,
)
from src.container import Container
from src.domain.observability.diagnostic import diagnose
from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.models.bot_model import BotModel
from src.infrastructure.db.models.rag_eval_model import RAGEvalModel
from src.infrastructure.db.models.rag_trace_model import RAGTraceModel
from src.infrastructure.db.models.tenant_model import TenantModel
from src.infrastructure.db.models.usage_record_model import UsageRecordModel
from src.interfaces.api.deps import require_role

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
@inject
async def list_evaluations(
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant_id: str | None = Query(default=None),
    layer: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=1),
    get_rules_uc: GetDiagnosticRulesUseCase = Depends(
        Provide[Container.get_diagnostic_rules_use_case]
    ),
):
    rule_config = await get_rules_uc.execute()

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
                "diagnostic_hints": [
                    {
                        "category": h.category,
                        "severity": h.severity,
                        "dimension": h.dimension,
                        "message": h.message,
                        "suggestion": h.suggestion,
                    }
                    for h in diagnose(r.dimensions or [], rule_config=rule_config)
                ],
            }
            for r in rows
        ],
    }


@router.get("/token-usage")
async def get_token_usage(
    days: int = Query(default=30, ge=1, le=365),
    tenant_id: str | None = Query(default=None),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session_factory() as session:
        stmt = (
            select(
                UsageRecordModel.tenant_id,
                TenantModel.name.label("tenant_name"),
                UsageRecordModel.bot_id,
                BotModel.name.label("bot_name"),
                UsageRecordModel.model,
                func.sum(UsageRecordModel.input_tokens).label("input_tokens"),
                func.sum(UsageRecordModel.output_tokens).label("output_tokens"),
                func.sum(UsageRecordModel.total_tokens).label("total_tokens"),
                func.sum(UsageRecordModel.estimated_cost).label("estimated_cost"),
                func.count().label("message_count"),
            )
            .outerjoin(
                BotModel,
                UsageRecordModel.bot_id == BotModel.id,
            )
            .outerjoin(
                TenantModel,
                UsageRecordModel.tenant_id == TenantModel.id,
            )
            .where(UsageRecordModel.created_at >= since)
        )

        if tenant_id:
            stmt = stmt.where(UsageRecordModel.tenant_id == tenant_id)

        stmt = stmt.group_by(
            UsageRecordModel.tenant_id,
            TenantModel.name,
            UsageRecordModel.bot_id,
            BotModel.name,
            UsageRecordModel.model,
        ).order_by(func.sum(UsageRecordModel.estimated_cost).desc())

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


# -----------------------------------------------------------------------
# Diagnostic Rules CRUD
# -----------------------------------------------------------------------


class SingleRuleSchema(BaseModel):
    dimension: str
    threshold: float
    category: str
    severity: str
    message: str
    suggestion: str


class ComboRuleSchema(BaseModel):
    dim_a: str
    op_a: str
    threshold_a: float
    dim_b: str
    op_b: str
    threshold_b: float
    category: str
    severity: str
    dimension: str
    message: str
    suggestion: str


class _DiagnosticRulesBody(BaseModel):
    single_rules: list[SingleRuleSchema]
    combo_rules: list[ComboRuleSchema]


@router.get("/diagnostic-rules")
@inject
async def get_diagnostic_rules(
    use_case: GetDiagnosticRulesUseCase = Depends(
        Provide[Container.get_diagnostic_rules_use_case]
    ),
):
    config = await use_case.execute()
    return {
        "id": config.id,
        "single_rules": config.single_rules,
        "combo_rules": config.combo_rules,
        "updated_at": config.updated_at.isoformat(),
    }


@router.put("/diagnostic-rules")
@inject
async def update_diagnostic_rules(
    body: _DiagnosticRulesBody,
    use_case: UpdateDiagnosticRulesUseCase = Depends(
        Provide[Container.update_diagnostic_rules_use_case]
    ),
):
    config = await use_case.execute(
        UpdateDiagnosticRulesCommand(
            single_rules=[r.model_dump() for r in body.single_rules],
            combo_rules=[r.model_dump() for r in body.combo_rules],
        )
    )
    return {
        "id": config.id,
        "single_rules": config.single_rules,
        "combo_rules": config.combo_rules,
        "updated_at": config.updated_at.isoformat(),
    }


@router.post("/diagnostic-rules/reset")
@inject
async def reset_diagnostic_rules(
    use_case: ResetDiagnosticRulesUseCase = Depends(
        Provide[Container.reset_diagnostic_rules_use_case]
    ),
):
    config = await use_case.execute()
    return {
        "id": config.id,
        "single_rules": config.single_rules,
        "combo_rules": config.combo_rules,
        "updated_at": config.updated_at.isoformat(),
    }


# -----------------------------------------------------------------------
# Log Retention Policy CRUD + Execute
# -----------------------------------------------------------------------


class _LogRetentionBody(BaseModel):
    enabled: bool = True
    retention_days: int = 30
    cleanup_hour: int = 3
    cleanup_interval_hours: int = 24


def _policy_to_dict(policy):
    return {
        "id": policy.id,
        "enabled": policy.enabled,
        "retention_days": policy.retention_days,
        "cleanup_hour": policy.cleanup_hour,
        "cleanup_interval_hours": policy.cleanup_interval_hours,
        "last_cleanup_at": (
            policy.last_cleanup_at.isoformat() if policy.last_cleanup_at else None
        ),
        "deleted_count_last": policy.deleted_count_last,
        "updated_at": policy.updated_at.isoformat(),
    }


@router.get("/log-retention")
@inject
async def get_log_retention(
    _: object = Depends(require_role("system_admin")),
    use_case: GetLogRetentionPolicyUseCase = Depends(
        Provide[Container.get_log_retention_policy_use_case]
    ),
):
    policy = await use_case.execute()
    return _policy_to_dict(policy)


@router.put("/log-retention")
@inject
async def update_log_retention(
    body: _LogRetentionBody,
    _: object = Depends(require_role("system_admin")),
    use_case: UpdateLogRetentionPolicyUseCase = Depends(
        Provide[Container.update_log_retention_policy_use_case]
    ),
):
    policy = await use_case.execute(
        UpdateLogRetentionPolicyCommand(
            enabled=body.enabled,
            retention_days=body.retention_days,
            cleanup_hour=body.cleanup_hour,
            cleanup_interval_hours=body.cleanup_interval_hours,
        )
    )
    return _policy_to_dict(policy)


@router.post("/log-retention/execute")
@inject
async def execute_log_cleanup(
    _: object = Depends(require_role("system_admin")),
    use_case: ExecuteLogCleanupUseCase = Depends(
        Provide[Container.execute_log_cleanup_use_case]
    ),
):
    deleted = await use_case.execute()
    return {"deleted_count": deleted}
