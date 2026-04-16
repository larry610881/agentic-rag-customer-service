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
from src.application.bot.get_bot_use_case import GetBotUseCase
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.container import Container
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant
from src.interfaces.api.streaming_errors import classify_streaming_error

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


class ToolCallInfo(BaseModel):
    tool_name: str
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
    usage: TokenUsageResponse | None = None


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
    get_bot: GetBotUseCase = Depends(Provide[Container.get_bot_use_case]),
) -> ChatResponse:
    effective_tenant_id = tenant.tenant_id
    if tenant.role == "system_admin" and request.bot_id:
        try:
            bot = await get_bot.execute(request.bot_id)
        except EntityNotFoundError:
            raise HTTPException(status_code=404, detail="Bot not found")
        effective_tenant_id = bot.tenant_id

    result = await use_case.execute(
        SendMessageCommand(
            tenant_id=effective_tenant_id,
            kb_id=request.knowledge_base_id or "",
            message=request.message,
            conversation_id=request.conversation_id,
            bot_id=request.bot_id,
            identity_source="web",
        )
    )

    await record_usage.execute(
        tenant_id=tenant.tenant_id,
        request_type="chat_web",
        usage=result.usage,
        bot_id=request.bot_id,
    )

    usage_resp = None
    if result.usage:
        usage_resp = TokenUsageResponse(
            model=result.usage.model,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            total_tokens=result.usage.total_tokens,
            estimated_cost=result.usage.estimated_cost,
        )

    return ChatResponse(
        answer=result.answer,
        conversation_id=result.conversation_id,
        tool_calls=[
            ToolCallInfo(
                tool_name=tc["tool_name"],
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
        usage=usage_resp,
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
    get_bot: GetBotUseCase = Depends(Provide[Container.get_bot_use_case]),
) -> StreamingResponse:
    effective_tenant_id = tenant.tenant_id
    if tenant.role == "system_admin" and request.bot_id:
        try:
            bot = await get_bot.execute(request.bot_id)
        except EntityNotFoundError:
            raise HTTPException(status_code=404, detail="Bot not found")
        effective_tenant_id = bot.tenant_id

    command = SendMessageCommand(
        tenant_id=effective_tenant_id,
        kb_id=request.knowledge_base_id or "",
        message=request.message,
        conversation_id=request.conversation_id,
        bot_id=request.bot_id,
        identity_source="web",
    )

    async def event_generator():
        # --- TEST TRIGGER: remove before production ---
        if command.message == "test-back":
            import traceback as _tb

            from src.application.observability.error_event_use_cases import (
                ReportErrorCommand,
            )
            from src.infrastructure.notification.dispatch_helper import (
                dispatch_error_notification,
            )

            # Simulate a realistic traceback
            try:
                raise RuntimeError(
                    "MilvusClient: Connection refused (connect ECONNREFUSED 127.0.0.1:19530)"
                )
            except RuntimeError:
                fake_stack = _tb.format_exc()

            report_uc = Container.report_error_use_case()
            event = await report_uc.execute(
                ReportErrorCommand(
                    source="backend",
                    error_type="RuntimeError",
                    message="MilvusClient: Connection refused (connect ECONNREFUSED 127.0.0.1:19530)",
                    stack_trace=fake_stack,
                    path="/api/v1/agent/chat/stream",
                    method="POST",
                    status_code=500,
                    tenant_id=command.tenant_id,
                    extra={
                        "bot_id": command.bot_id,
                        "milvus_host": "localhost",
                        "milvus_port": 19530,
                        "retry_count": 3,
                    },
                )
            )
            asyncio.create_task(dispatch_error_notification(event))
            yield f"data: {json.dumps({'type': 'error', 'message': '[Test] 後端模擬錯誤已觸發'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
        # --- END TEST TRIGGER ---

        usage_data: dict | None = None
        try:
            async for event in use_case.execute_stream(command):
                if event.get("type") == "usage":
                    usage_data = event
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("agent.chat.stream.error")
            error_msg = classify_streaming_error(exc)
            error_payload = {"type": "error", "message": error_msg}
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

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
                        request_type="chat_web",
                        usage=usage,
                        bot_id=request.bot_id,
                    )
                except Exception:
                    logger.exception("agent.chat.stream.record_usage_error")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# === Built-in tools registry ===


class BuiltInToolItem(BaseModel):
    name: str
    label: str
    description: str
    requires_kb: bool


BUILT_IN_TOOLS: list[BuiltInToolItem] = [
    BuiltInToolItem(
        name="rag_query",
        label="知識庫查詢",
        description="對 bot 連結的知識庫做向量檢索，適合一般文字問答。",
        requires_kb=True,
    ),
    BuiltInToolItem(
        name="query_dm_with_image",
        label="DM 圖卡查詢",
        description=(
            "對 catalog PDF 知識庫（如家樂福 DM）檢索，命中頁面以 LINE Flex "
            "carousel 推送原始 PNG 圖卡，適合促銷 / 商品查詢場景。"
        ),
        requires_kb=True,
    ),
]


@router.get("/built-in-tools", response_model=list[BuiltInToolItem])
async def list_built_in_tools(
    _: CurrentTenant = Depends(get_current_tenant),
) -> list[BuiltInToolItem]:
    """列出系統內建可啟用的 tools，供 bot 編輯 UI 顯示多選清單。"""
    return BUILT_IN_TOOLS
