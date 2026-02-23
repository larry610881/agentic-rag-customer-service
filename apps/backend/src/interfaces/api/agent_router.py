"""Agent Chat API 端點"""

import json

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.container import Container
from src.interfaces.api.deps import CurrentTenant, get_current_tenant

router = APIRouter(
    prefix="/api/v1/agent",
    tags=["agent"],
)


class ChatRequest(BaseModel):
    knowledge_base_id: str
    message: str
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
) -> ChatResponse:
    result = await use_case.execute(
        SendMessageCommand(
            tenant_id=tenant.tenant_id,
            kb_id=request.knowledge_base_id,
            message=request.message,
            conversation_id=request.conversation_id,
        )
    )

    await record_usage.execute(
        tenant_id=tenant.tenant_id,
        request_type="agent",
        usage=result.usage,
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
) -> StreamingResponse:
    async def event_generator():
        async for chunk in use_case.execute_stream(
            SendMessageCommand(
                tenant_id=tenant.tenant_id,
                kb_id=request.knowledge_base_id,
                message=request.message,
                conversation_id=request.conversation_id,
            )
        ):
            event = {"type": "token", "content": chunk}
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
