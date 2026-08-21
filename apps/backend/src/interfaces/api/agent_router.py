"""Agent Chat API 端點"""

import asyncio
import json
import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, get_current_tenant
from src.interfaces.api.streaming_errors import classify_streaming_error
from src.interfaces.api.usage_context import UsageContext, get_usage_context

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/agent",
    tags=["agent"],
)


class ChatRequest(BaseModel):
    message: str
    bot_id: str | None = None
    knowledge_base_id: str | None = None
    conversation_id: str | None = None
    # 來源識別（"web" / "widget" / "line" / "studio"），影響 agent_execution_traces.source；
    # 預設 "web" 對應後台 chat / Studio 試運轉等網頁來源。
    identity_source: str | None = None
    # Issue #54 Phase C — 影子執行（閘門驗證 / Playground）。
    # 授權：必須帶合法 eval 標記 header（X-Usage-Category ∈ eval 類 + admin role），
    # 否則 403。widget/LINE 不走本 router，天然隔離。
    config_override: dict | None = None
    test_mode: bool = False
    history_override: list[dict] | None = None


class ToolCallInfo(BaseModel):
    tool_name: str
    label: str = ""  # Backend resolve 後的中文顯示名稱，空值時前端 fallback 為 tool_name
    reasoning: str


class SourceResponse(BaseModel):
    document_name: str
    content_snippet: str
    score: float


class TokenUsageResponse(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    tool_calls: list[ToolCallInfo]
    sources: list[SourceResponse]
    structured_content: dict | None = None
    usage: TokenUsageResponse | None = None
    trace_id: str | None = None       # test_mode 影子執行才填
    trace_nodes: list[dict] | None = None
    # Sprint A++ Guard UX: 只暴露給 Studio（identity_source="studio"）
    # widget / LINE / web 路徑會被 sanitize 成 None 避免洩露防禦邏輯
    guard_blocked: str | None = None
    guard_rule_matched: str | None = None


# Studio 以外的 identity_source 都視為 end-user 介面，guard_blocked
# 必須清空避免洩露安全規則的存在。
_EVAL_USAGE_CATEGORIES = frozenset(
    {"eval_gate", "prompt_optimize", "playground"}
)


def _require_shadow_authorized(
    request: ChatRequest, usage_ctx: UsageContext
) -> None:
    """Issue #54 Phase C — 影子執行是新攻擊面：body 帶 override/test_mode
    但 usage 標記未通過授權（header 缺失/分類不合法/role 不足）→ 403。"""
    wants_shadow = (
        request.config_override is not None
        or request.test_mode
        or request.history_override is not None
    )
    if wants_shadow and usage_ctx.request_type not in _EVAL_USAGE_CATEGORIES:
        raise HTTPException(
            status_code=403,
            detail="config_override/test_mode requires a valid eval usage "
            "marker (X-Usage-Category + admin role)",
        )


_GUARD_DETAIL_ROLES = frozenset({"system_admin", "tenant_admin"})


def _can_see_guard_details(role: str | None) -> bool:
    """M13：guard_blocked 的 rule_matched 是平台防護規則原文（正規讀取需 admin）。
    原本以 body 自報的 identity_source="studio" 判定，任何租戶使用者都能偽造以枚舉
    規則。改以 JWT role 判定——只有 admin（Studio 使用者本就是）看得到細節。"""
    return role in _GUARD_DETAIL_ROLES


def _maybe_expose_guard(result_guard_blocked, result_guard_rule, role):
    """返回 (guard_blocked, guard_rule) tuple 或 (None, None)。"""
    if _can_see_guard_details(role):
        return result_guard_blocked, result_guard_rule
    return None, None


@router.post("/chat", response_model=ChatResponse)
@inject
async def agent_chat(
    request: ChatRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: SendMessageUseCase = Depends(
        Provide[Container.send_message_use_case]
    ),
    record_usage: RecordUsageUseCase = Depends(
        Provide[Container.record_usage_use_case]
    ),
    usage_ctx: UsageContext = Depends(get_usage_context),
) -> ChatResponse:
    # S-Gov.3: admin 一律以自己的 tenant_id (SYSTEM_TENANT_ID) 發訊息；
    # 跨租戶測試流程請走系統管理專用端點（尚未實作，另立 issue）。
    identity_source = request.identity_source or "web"
    _require_shadow_authorized(request, usage_ctx)
    result = await use_case.execute(
        SendMessageCommand(
            tenant_id=tenant.tenant_id,
            kb_id=request.knowledge_base_id or "",
            message=request.message,
            conversation_id=request.conversation_id,
            bot_id=request.bot_id,
            identity_source=identity_source,
            config_override=request.config_override,
            test_mode=request.test_mode,
            history_override=request.history_override,
        )
    )

    # Sprint A++: Studio 才暴露 guard flag
    guard_blocked, guard_rule_matched = _maybe_expose_guard(
        result.guard_blocked, result.guard_rule_matched, tenant.role
    )

    # 記帳 fail-open：帳務失敗不得炸使用者請求（工程約束；spec §7.3 修債）
    try:
        await record_usage.execute(
            tenant_id=tenant.tenant_id,
            request_type=usage_ctx.request_type,
            usage=result.usage,
            bot_id=request.bot_id,
            message_id=result.message_id,
            run_id=usage_ctx.run_id,
            config_version_id=result.config_version_id,
        )
    except Exception:
        logger.exception("agent.chat.record_usage_error")

    usage_resp = None
    if result.usage:
        usage_resp = TokenUsageResponse(
            model=result.usage.model,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
            estimated_cost=result.usage.estimated_cost,
        )

    sources_dicts = (
        [s.to_dict() for s in result.sources] if result.sources else None
    )
    structured_content: dict | None = None
    if result.contact or sources_dicts:
        structured_content = {
            "contact": result.contact,
            "sources": sources_dicts,
        }

    return ChatResponse(
        answer=result.answer,
        conversation_id=result.conversation_id,
        trace_id=result.trace_id,
        trace_nodes=result.trace_nodes,
        tool_calls=[
            ToolCallInfo(
                tool_name=tc["tool_name"],
                label=tc.get("label", ""),
                reasoning=tc.get("reasoning", ""),
            )
            for tc in result.tool_calls
        ],
        sources=[
            SourceResponse(
                document_name=s.document_name,
                content_snippet=s.content_snippet,
                score=s.score,
            )
            for s in result.sources
        ],
        structured_content=structured_content,
        usage=usage_resp,
        guard_blocked=guard_blocked,
        guard_rule_matched=guard_rule_matched,
    )


@router.post("/chat/stream")
@inject
async def agent_chat_stream(
    request: ChatRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: SendMessageUseCase = Depends(
        Provide[Container.send_message_use_case]
    ),
    record_usage: RecordUsageUseCase = Depends(
        Provide[Container.record_usage_use_case]
    ),
    usage_ctx: UsageContext = Depends(get_usage_context),
) -> StreamingResponse:
    # S-Gov.3: admin 一律以自己的 tenant_id (SYSTEM_TENANT_ID) 發訊息；
    # 跨租戶測試流程請走系統管理專用端點（尚未實作，另立 issue）。
    _require_shadow_authorized(request, usage_ctx)
    command = SendMessageCommand(
        tenant_id=tenant.tenant_id,
        kb_id=request.knowledge_base_id or "",
        message=request.message,
        conversation_id=request.conversation_id,
        bot_id=request.bot_id,
        identity_source=request.identity_source or "web",
        config_override=request.config_override,
        test_mode=request.test_mode,
        history_override=request.history_override,
    )

    async def event_generator():
        # Sprint A++: 只有 Studio 才看得到 guard_blocked event，end-user 介面
        # (widget/LINE/web bot) 不暴露防禦邏輯存在
        # M13：guard 細節暴露改以 JWT role 判定（非 body 自報的 identity_source）
        is_studio = _can_see_guard_details(tenant.role)

        usage_data: dict | None = None
        assistant_message_id: str | None = None
        config_version_id: str | None = None
        try:
            async for event in use_case.execute_stream(command):
                if event.get("type") == "usage":
                    usage_data = event
                    continue
                # S-ConvInsights.1: 捕獲 assistant message_id 供 RecordUsage 用
                if event.get("type") == "message_id":
                    assistant_message_id = event.get("message_id")
                if event.get("type") == "config_version":
                    config_version_id = event.get("config_version_id")
                    continue  # 內部事件，不下發前端
                # Sprint A++: strip guard_blocked event for end-user 介面
                if event.get("type") == "guard_blocked" and not is_studio:
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("agent.chat.stream.error")
            error_msg = classify_streaming_error(exc)
            # Phase 1: 標記 trace 最後一筆節點為 failed，讓 Studio 紅框可見
            from src.infrastructure.observability.agent_trace_collector import (
                AgentTraceCollector,
            )
            AgentTraceCollector.mark_current_failed(error_msg)

            # Phase 1: 同時持久化 trace（exception 路徑 use_case 來不及 _persist_agent_trace）
            # + 帶 trace_id 給前端 fetch 完整 DAG（含 failed 節點）
            failed_trace_id = ""
            _trace = AgentTraceCollector.current()
            if _trace is not None:
                failed_trace_id = _trace.trace_id
                try:
                    await use_case._persist_agent_trace(  # noqa: SLF001
                        conversation_id=command.conversation_id,
                        message_id=None,
                        latency_ms=0,
                        source=command.identity_source or "web",
                    )
                except Exception:
                    logger.exception("agent.chat.stream.persist_failed_trace_error")

            error_payload = {"type": "error", "message": error_msg}
            done_payload: dict = {"type": "done"}
            if failed_trace_id:
                done_payload["trace_id"] = failed_trace_id
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

        # Record usage after stream completes
        if usage_data:
            from src.infrastructure.langgraph.usage import (
                extract_usage_from_accumulated,
            )

            usage = extract_usage_from_accumulated(usage_data)
            if usage is not None:
                try:
                    await record_usage.execute(
                        tenant_id=tenant.tenant_id,
                        request_type=usage_ctx.request_type,
                        usage=usage,
                        bot_id=request.bot_id,
                        message_id=assistant_message_id,
                        run_id=usage_ctx.run_id,
                        config_version_id=config_version_id,
                    )
                except Exception:
                    logger.exception("agent.chat.stream.record_usage_error")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# === Built-in tools registry (tenant-aware) ===


class BuiltInToolItem(BaseModel):
    name: str
    label: str
    description: str
    requires_kb: bool
    scope: str | None = None  # admin-only
    tenant_ids: list[str] | None = None  # admin-only


@router.get("/built-in-tools", response_model=list[BuiltInToolItem])
@inject
async def list_built_in_tools(
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case=Depends(Provide[Container.list_built_in_tools_use_case]),
) -> list[BuiltInToolItem]:
    """列出 current user 可使用的 built-in tools。

    system_admin → 所有工具（含 scope 與白名單，用於管理 UI）
    一般租戶 → global + 白名單包含自己 tenant_id 的工具
    """
    is_admin = tenant.role == "system_admin"
    tools = await use_case.execute(
        tenant_id=tenant.tenant_id or None,
        is_admin=is_admin,
    )
    return [
        BuiltInToolItem(
            name=t.name,
            label=t.label,
            description=t.description,
            requires_kb=t.requires_kb,
            scope=t.scope if is_admin else None,
            tenant_ids=list(t.tenant_ids) if is_admin else None,
        )
        for t in tools
    ]
