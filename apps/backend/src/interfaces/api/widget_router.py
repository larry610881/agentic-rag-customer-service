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
from src.container import Container
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.tenant.repository import TenantRepository

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


class WidgetConfigResponse(BaseModel):
    name: str
    description: str
    keep_history: bool
    avatar_type: str = "none"
    avatar_model_url: str = ""
    welcome_message: str = ""
    placeholder_text: str = ""
    greeting_messages: list[str] = []
    greeting_animation: str = "fade"


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


def _set_cors_headers(response, origin: str | None, bot: Bot) -> None:
    """Set dynamic CORS headers based on bot's allowed origins."""
    if origin and origin in bot.widget_allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"


@router.options("/{short_code}/chat/stream")
@router.options("/{short_code}/config")
@router.options("/{short_code}/feedback")
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
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Max-Age"] = "3600"
    return resp


@router.get("/{short_code}/config", response_model=WidgetConfigResponse)
@inject
async def widget_config(
    short_code: str,
    request: Request,
    response: Response,
    bot_repo: BotRepository = Depends(Provide[Container.bot_repository]),
    tenant_repo: TenantRepository = Depends(Provide[Container.tenant_repository]),
) -> WidgetConfigResponse:
    """Public endpoint: get bot display config."""
    origin = request.headers.get("origin")
    bot = await validate_widget_bot(short_code, origin, bot_repo)

    _set_cors_headers(response, origin, bot)

    # Check tenant permission for widget avatar
    avatar_type = bot.avatar_type
    avatar_model_url = bot.avatar_model_url
    tenant = await tenant_repo.find_by_id(bot.tenant_id)
    if not tenant or not tenant.allowed_widget_avatar:
        avatar_type = "none"
        avatar_model_url = ""

    return WidgetConfigResponse(
        name=bot.name,
        description=bot.description,
        keep_history=bot.widget_keep_history,
        avatar_type=avatar_type,
        avatar_model_url=avatar_model_url,
        welcome_message=bot.widget_welcome_message,
        placeholder_text=bot.widget_placeholder_text,
        greeting_messages=bot.widget_greeting_messages,
        greeting_animation=bot.widget_greeting_animation,
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
) -> StreamingResponse:
    """Public endpoint: SSE streaming chat."""
    origin = request.headers.get("origin")
    bot = await validate_widget_bot(short_code, origin, bot_repo)

    command = SendMessageCommand(
        tenant_id=bot.tenant_id,
        bot_id=bot.id.value,
        message=body.message,
        conversation_id=body.conversation_id if bot.widget_keep_history else None,
    )

    async def event_generator():
        try:
            async for event in use_case.execute_stream(command):
                # Skip usage events (internal)
                if event.get("type") == "usage":
                    continue
                # Filter out conversation_id when keep_history is disabled
                if not bot.widget_keep_history and event.get("type") == "conversation_id":
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception("widget.chat.stream.error")
            error_msg = str(exc)
            if "429" in error_msg:
                error_msg = "API 額度已用完，請稍後再試"
            error_payload = {"type": "error", "message": error_msg}
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

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
