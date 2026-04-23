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
from src.infrastructure.db.models.agent_trace_model import AgentExecutionTraceModel
from src.infrastructure.db.models.bot_model import BotModel
from src.infrastructure.db.models.knowledge_base_model import KnowledgeBaseModel
from src.infrastructure.db.models.rag_eval_model import RAGEvalModel
from src.infrastructure.db.models.tenant_model import TenantModel
from src.infrastructure.db.models.usage_record_model import UsageRecordModel
from src.interfaces.api.deps import CurrentTenant, get_current_tenant, require_role

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])


def _effective_tenant_filter(
    tenant: CurrentTenant, tenant_id: str | None
) -> str | None:
    """S-Gov.3 tenant filter resolution for observability read endpoints.

    Observability 是 admin 本職就該跨租戶觀察的場景，所以這裡的解析跟一般
    保護性 helper 不同：

    - admin (system_admin):
        - tenant_id 指定 → 過濾該租戶
        - tenant_id 未指定（None）→ 回傳 None（**不過濾**，看全部租戶）
    - 一般租戶：強制用自己的 tenant_id，忽略 query param（防止越權）

    呼叫端必須對 None 結果做條件式 WHERE：`if tid: stmt.where(...)`。
    """
    if tenant.role == "system_admin":
        return tenant_id  # None → 全部租戶（觀測場景）
    return tenant.tenant_id



@router.get("/evaluations")
@inject
async def list_evaluations(
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant_id: str | None = Query(default=None),
    layer: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=1),
    tenant: CurrentTenant = Depends(get_current_tenant),
    get_rules_uc: GetDiagnosticRulesUseCase = Depends(
        Provide[Container.get_diagnostic_rules_use_case]
    ),
):
    effective_tid = _effective_tenant_filter(tenant, tenant_id)
    rule_config = await get_rules_uc.execute()

    async with async_session_factory() as session:
        stmt = select(RAGEvalModel).order_by(RAGEvalModel.created_at.desc())
        count_stmt = select(func.count()).select_from(RAGEvalModel)

        # admin + 未指定 tenant_id → effective_tid 為 None，不加 WHERE → 看全部租戶
        if effective_tid is not None:
            stmt = stmt.where(RAGEvalModel.tenant_id == effective_tid)
            count_stmt = count_stmt.where(RAGEvalModel.tenant_id == effective_tid)
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


@router.get("/agent-traces")
async def list_agent_traces(
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant_id: str | None = Query(default=None),
    agent_mode: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    # S-Gov.6a: 7 個新 filter
    source: str | None = Query(default=None, description="web | widget | line"),
    bot_id: str | None = Query(default=None),
    outcome: str | None = Query(
        default=None, description="success | failed | partial"
    ),
    min_total_ms: float | None = Query(default=None, ge=0),
    max_total_ms: float | None = Query(default=None, ge=0),
    min_total_tokens: int | None = Query(default=None, ge=0),
    max_total_tokens: int | None = Query(default=None, ge=0),
    keyword: str | None = Query(default=None, description="ILIKE on nodes::text"),
    group_by_conversation: bool = Query(
        default=False, description="True → grouped 結構 by conversation_id"
    ),
    tenant: CurrentTenant = Depends(get_current_tenant),
):
    from src.application.observability.agent_trace_queries import (
        TraceFilters,
        build_where,
        list_traces_grouped_by_conversation,
        trace_to_dict,
    )

    effective_tid = _effective_tenant_filter(tenant, tenant_id)
    filters = TraceFilters(
        tenant_id=effective_tid,
        agent_mode=agent_mode,
        conversation_id=conversation_id,
        date_from=date_from,
        date_to=date_to,
        source=source,
        bot_id=bot_id,
        outcome=outcome,
        min_total_ms=min_total_ms,
        max_total_ms=max_total_ms,
        min_total_tokens=min_total_tokens,
        max_total_tokens=max_total_tokens,
        keyword=keyword,
    )

    async with async_session_factory() as session:
        if group_by_conversation:
            groups, total = await list_traces_grouped_by_conversation(
                session, filters=filters, limit=limit, offset=offset,
            )
            return {
                "total": total,
                "grouped": True,
                "items": [
                    {
                        "conversation_id": g.conversation_id,
                        "trace_count": g.trace_count,
                        "first_user_message": g.first_user_message,
                        "last_assistant_answer": g.last_assistant_answer,
                        "summary": g.summary,
                        "first_at": g.first_at.isoformat()
                        if g.first_at else None,
                        "last_at": g.last_at.isoformat()
                        if g.last_at else None,
                        "traces": g.traces,
                    }
                    for g in groups
                ],
            }

        # Flat mode
        T = AgentExecutionTraceModel  # noqa: N806
        where = build_where(filters)
        stmt = (
            select(T)
            .where(*where)
            .order_by(T.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(T).where(*where)

        total = (await session.execute(count_stmt)).scalar() or 0
        rows = (await session.execute(stmt)).scalars().all()

    return {
        "total": total,
        "grouped": False,
        "items": [trace_to_dict(r) for r in rows],
    }


@router.get("/agent-traces/{trace_id}")
async def get_agent_trace(
    trace_id: str,
    tenant: CurrentTenant = Depends(get_current_tenant),
):
    async with async_session_factory() as session:
        stmt = select(AgentExecutionTraceModel).where(
            AgentExecutionTraceModel.trace_id == trace_id
        )
        row = (await session.execute(stmt)).scalar_one_or_none()

    if row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Agent trace not found")

    # S-Gov.3: 非 admin 只能看自己 tenant 的 trace；admin 可跨租戶
    if tenant.role != "system_admin" and row.tenant_id != tenant.tenant_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Agent trace not found")

    return {
        "id": row.id,
        "trace_id": row.trace_id,
        "tenant_id": row.tenant_id,
        "message_id": row.message_id,
        "conversation_id": row.conversation_id,
        "agent_mode": row.agent_mode,
        "source": getattr(row, "source", ""),
        "llm_model": getattr(row, "llm_model", ""),
        "llm_provider": getattr(row, "llm_provider", ""),
        "bot_id": getattr(row, "bot_id", None),
        "nodes": row.nodes,
        "total_ms": row.total_ms,
        "total_tokens": row.total_tokens,
        "outcome": getattr(row, "outcome", None),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/token-usage")
async def get_token_usage(
    days: int = Query(default=30, ge=1, le=365),
    tenant_id: str | None = Query(default=None),
    tenant: CurrentTenant = Depends(get_current_tenant),
):
    effective_tid = _effective_tenant_filter(tenant, tenant_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session_factory() as session:
        stmt = (
            select(
                UsageRecordModel.tenant_id,
                TenantModel.name.label("tenant_name"),
                UsageRecordModel.bot_id,
                BotModel.name.label("bot_name"),
                UsageRecordModel.kb_id,
                KnowledgeBaseModel.name.label("kb_name"),
                UsageRecordModel.model,
                UsageRecordModel.request_type,
                func.sum(UsageRecordModel.input_tokens).label("input_tokens"),
                func.sum(UsageRecordModel.output_tokens).label("output_tokens"),
                # S-Token-Gov.6: total_tokens 已從 DB column 改為 @property。
                # SUM 改由其他欄位合成。
                (
                    func.sum(UsageRecordModel.input_tokens)
                    + func.sum(UsageRecordModel.output_tokens)
                    + func.sum(UsageRecordModel.cache_read_tokens)
                    + func.sum(UsageRecordModel.cache_creation_tokens)
                ).label("total_tokens"),
                func.sum(UsageRecordModel.estimated_cost).label("estimated_cost"),
                func.sum(UsageRecordModel.cache_read_tokens).label("cache_read_tokens"),
                func.sum(UsageRecordModel.cache_creation_tokens).label("cache_creation_tokens"),
                func.count().label("message_count"),
            )
            .outerjoin(
                BotModel,
                UsageRecordModel.bot_id == BotModel.id,
            )
            .outerjoin(
                KnowledgeBaseModel,
                UsageRecordModel.kb_id == KnowledgeBaseModel.id,
            )
            .outerjoin(
                TenantModel,
                UsageRecordModel.tenant_id == TenantModel.id,
            )
            .where(UsageRecordModel.created_at >= since)
        )
        # admin + 未指定 tenant_id → effective_tid 為 None，不加 WHERE → 看全部租戶
        if effective_tid is not None:
            stmt = stmt.where(UsageRecordModel.tenant_id == effective_tid)

        stmt = stmt.group_by(
            UsageRecordModel.tenant_id,
            TenantModel.name,
            UsageRecordModel.bot_id,
            BotModel.name,
            UsageRecordModel.kb_id,
            KnowledgeBaseModel.name,
            UsageRecordModel.model,
            UsageRecordModel.request_type,
        ).order_by(func.sum(UsageRecordModel.estimated_cost).desc())

        rows = (await session.execute(stmt)).all()

    return {
        "items": [
            {
                "tenant_id": r.tenant_id,
                "tenant_name": r.tenant_name or "(未知租戶)",
                "bot_id": r.bot_id,
                "bot_name": r.bot_name,
                "kb_id": r.kb_id,
                "kb_name": r.kb_name,
                "model": r.model,
                "request_type": r.request_type,
                "input_tokens": r.input_tokens or 0,
                "output_tokens": r.output_tokens or 0,
                "total_tokens": r.total_tokens or 0,
                "estimated_cost": float(r.estimated_cost or 0),
                "cache_read_tokens": r.cache_read_tokens or 0,
                "cache_creation_tokens": r.cache_creation_tokens or 0,
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
    _: CurrentTenant = Depends(get_current_tenant),
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
    _: CurrentTenant = Depends(require_role("system_admin")),
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
    _: CurrentTenant = Depends(require_role("system_admin")),
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
