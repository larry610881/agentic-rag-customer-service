"""Widget 公開 Chat API — 外部網站嵌入式聊天"""

import json
import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.conversation.submit_feedback_use_case import (
    SubmitFeedbackCommand,
    SubmitFeedbackUseCase,
)
from src.application.knowledge.view_document_use_case import (
    ViewDocumentUseCase,
)
from src.application.observability.error_event_use_cases import (
    ReportErrorCommand,
    ReportErrorUseCase,
)
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.container import Container
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.knowledge.repository import DocumentRepository
from src.interfaces.api.streaming_errors import classify_streaming_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/widget", tags=["widget"])


class WidgetChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    metadata: dict | None = None  # 預留：未來帶身份 token 時用


class WidgetFeedbackRequest(BaseModel):
    conversation_id: str
    message_id: str
    rating: str  # "thumbs_up" | "thumbs_down"
    comment: str | None = None
    tags: list[str] = []


class WidgetErrorRequest(BaseModel):
    error_type: str
    message: str
    stack_trace: str | None = None
    path: str | None = None
    user_agent: str | None = None


class WidgetConfigResponse(BaseModel):
    name: str
    description: str
    keep_history: bool
    show_sources: bool = True
    welcome_message: str = ""
    placeholder_text: str = ""
    greeting_messages: list[str] = []
    greeting_animation: str = "fade"
    fab_icon_url: str = ""


async def validate_widget_bot(
    short_code: str,
    origin: str | None,
    bot_repo: BotRepository,
) -> Bot:
    """Validate widget access. Raises HTTPException on failure."""
    bot = await bot_repo.find_by_short_code(short_code)
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found",
        )
    if not bot.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bot is not active",
        )
    if not bot.widget_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Widget is not enabled for this bot",
        )
    # CORS origin check
    if bot.widget_allowed_origins:
        if not origin or origin not in bot.widget_allowed_origins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin not allowed",
            )
    return bot


def _widget_should_forward(
    event: dict, keep_history: bool, captured: dict
) -> bool:
    """決定 widget SSE 事件是否下發匿名前端，並側錄歸因欄位到 captured。

    - usage / config_version：內部事件，捕獲後不下發（H7 config_version；H8 歸因）。
    - guard_blocked：含命中規則原文（rule_matched，需 system_admin 才可正規讀取）與
      replacement，匿名通路不得外洩，否則可逐條探針枚舉整份防護規則（H7）。
    - message_id：捕獲供版本成效歸因（H8），仍下發以與 web 對齊。
    - conversation_id：keep_history 關閉時不下發。
    """
    etype = event.get("type")
    if etype == "usage":
        captured["usage"] = event
        return False
    if etype == "config_version":
        captured["config_version_id"] = event.get("config_version_id")
        return False
    if etype == "guard_blocked":
        return False
    if etype == "message_id":
        captured["message_id"] = event.get("message_id")
        return True
    if etype == "conversation_id" and not keep_history:
        return False
    return True


def _set_cors_headers(response, origin: str | None, bot: Bot) -> None:
    """Set dynamic CORS headers based on bot's allowed origins."""
    if origin and origin in bot.widget_allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Visitor-Id"


@router.options("/{short_code}/chat/stream")
@router.options("/{short_code}/config")
@router.options("/{short_code}/feedback")
@router.options("/{short_code}/error")
@inject
async def widget_cors_preflight(
    short_code: str,
    request: Request,
    bot_repo: BotRepository = Depends(Provide[Container.bot_repository]),
) -> StreamingResponse:
    """CORS preflight — dynamic allowed origin."""
    origin = request.headers.get("origin")
    bot = await bot_repo.find_by_short_code(short_code)

    from starlette.responses import Response

    resp = Response(status_code=204)
    if bot and bot.widget_enabled and origin and origin in bot.widget_allowed_origins:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Visitor-Id"
        resp.headers["Access-Control-Max-Age"] = "3600"
    return resp


@router.get("/{short_code}/config", response_model=WidgetConfigResponse)
@inject
async def widget_config(
    short_code: str,
    request: Request,
    response: Response,
    bot_repo: BotRepository = Depends(Provide[Container.bot_repository]),
) -> WidgetConfigResponse:
    """Public endpoint: get bot display config."""
    origin = request.headers.get("origin")
    bot = await validate_widget_bot(short_code, origin, bot_repo)

    _set_cors_headers(response, origin, bot)

    return WidgetConfigResponse(
        name=bot.name,
        description=bot.description,
        keep_history=bot.widget_keep_history,
        show_sources=bot.show_sources,
        welcome_message=bot.widget_welcome_message,
        placeholder_text=bot.widget_placeholder_text,
        greeting_messages=bot.widget_greeting_messages,
        greeting_animation=bot.widget_greeting_animation,
        fab_icon_url=bot.fab_icon_url,
    )


@router.post("/{short_code}/chat/stream")
@inject
async def widget_chat_stream(
    short_code: str,
    body: WidgetChatRequest,
    request: Request,
    bot_repo: BotRepository = Depends(Provide[Container.bot_repository]),
    use_case: SendMessageUseCase = Depends(
        Provide[Container.send_message_use_case]
    ),
    record_usage: RecordUsageUseCase = Depends(
        Provide[Container.record_usage_use_case]
    ),
) -> StreamingResponse:
    """Public endpoint: SSE streaming chat."""
    origin = request.headers.get("origin")
    bot = await validate_widget_bot(short_code, origin, bot_repo)

    visitor_id = request.headers.get("x-visitor-id")
    command = SendMessageCommand(
        tenant_id=bot.tenant_id,
        bot_id=bot.id.value,
        message=body.message,
        conversation_id=body.conversation_id if bot.widget_keep_history else None,
        visitor_id=visitor_id,
        # L6：widget 端點固定通路標記——無 X-Visitor-Id 時原本為 None，trace source
        # 會 fallback 成 "web"，通路別統計把 widget 流量算進 web。memory 身份解析
        # 仍以 visitor_id 為 gate（_resolve_and_load_memory 先檢查 visitor_id）。
        identity_source="widget",
    )

    async def event_generator():
        captured: dict = {}
        try:
            async for event in use_case.execute_stream(command):
                if _widget_should_forward(event, bot.widget_keep_history, captured):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("widget.chat.stream.error")
            error_msg = classify_streaming_error(exc)
            # L5：與 agent_router 對齊（channel parity）——標記+持久化 failed trace，
            # 否則 widget 通路的失敗不出現在 Studio 觀測頁，該輪 trace 直接丟失。
            from src.interfaces.api._streaming_failure import (
                persist_failed_stream_trace,
            )

            failed_trace_id = await persist_failed_stream_trace(
                use_case,
                conversation_id=command.conversation_id,
                source="widget",
                error_msg=error_msg,
            )
            error_payload = {"type": "error", "message": error_msg}
            done_payload: dict = {"type": "done"}
            if failed_trace_id:
                done_payload["trace_id"] = failed_trace_id
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

        # Record token usage after stream completes
        usage_data = captured.get("usage")
        if usage_data:
            from src.infrastructure.langgraph.usage import (
                extract_usage_from_accumulated,
            )

            usage = extract_usage_from_accumulated(usage_data)
            if usage is not None:
                try:
                    await record_usage.execute(
                        tenant_id=bot.tenant_id,
                        request_type="chat_widget",
                        usage=usage,
                        bot_id=bot.id.value,
                        message_id=captured.get("message_id"),  # H8
                        config_version_id=captured.get("config_version_id"),  # H8
                    )
                except Exception:
                    logger.exception("widget.chat.stream.record_usage_error")

    response = StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
    _set_cors_headers(response, origin, bot)
    return response


@router.post("/{short_code}/feedback", status_code=201)
@inject
async def widget_feedback(
    short_code: str,
    body: WidgetFeedbackRequest,
    request: Request,
    response: Response,
    bot_repo: BotRepository = Depends(Provide[Container.bot_repository]),
    use_case: SubmitFeedbackUseCase = Depends(
        Provide[Container.submit_feedback_use_case]
    ),
) -> dict:
    """Public endpoint: submit feedback from widget."""
    origin = request.headers.get("origin")
    bot = await validate_widget_bot(short_code, origin, bot_repo)

    command = SubmitFeedbackCommand(
        tenant_id=bot.tenant_id,
        conversation_id=body.conversation_id,
        message_id=body.message_id,
        channel="widget",
        rating=body.rating,
        comment=body.comment,
        tags=body.tags,
    )
    await use_case.execute(command)

    _set_cors_headers(response, origin, bot)
    return {"success": True}


@router.post("/{short_code}/error", status_code=201)
@inject
async def widget_error_report(
    short_code: str,
    body: WidgetErrorRequest,
    request: Request,
    response: Response,
    bot_repo: BotRepository = Depends(Provide[Container.bot_repository]),
    use_case: ReportErrorUseCase = Depends(
        Provide[Container.report_error_use_case]
    ),
) -> dict:
    """Public endpoint: report errors from widget."""
    origin = request.headers.get("origin")
    bot = await validate_widget_bot(short_code, origin, bot_repo)

    event = await use_case.execute(
        ReportErrorCommand(
            source="widget",
            error_type=body.error_type,
            message=body.message,
            stack_trace=body.stack_trace,
            path=body.path,
            user_agent=body.user_agent,
        )
    )

    _set_cors_headers(response, origin, bot)
    return {"id": event.id, "fingerprint": event.fingerprint}


@router.get("/{short_code}/documents/{doc_id}/view")
@inject
async def widget_view_document(
    short_code: str,
    doc_id: str,
    request: Request,
    bot_repo: BotRepository = Depends(Provide[Container.bot_repository]),
    doc_repo: DocumentRepository = Depends(
        Provide[Container.document_repository]
    ),
    use_case: ViewDocumentUseCase = Depends(
        Provide[Container.view_document_use_case]
    ),
) -> Response:
    """Public endpoint: view original document file (inline, no download)."""
    origin = request.headers.get("origin")
    bot = await validate_widget_bot(short_code, origin, bot_repo)

    if not bot.show_sources:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Source viewing is disabled for this bot",
        )

    # Verify document belongs to one of this bot's knowledge bases
    doc = await doc_repo.find_by_id(doc_id)
    if doc is None or doc.kb_id not in bot.knowledge_base_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    result = await use_case.execute(doc_id)

    resp = Response(
        content=result.content,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{result.filename}"'
        },
    )
    _set_cors_headers(resp, origin, bot)
    return resp
