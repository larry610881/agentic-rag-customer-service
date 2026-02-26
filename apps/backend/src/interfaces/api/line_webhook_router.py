"""LINE Webhook API 端點"""

import json

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.container import Container
from src.domain.line.entity import LinePostbackEvent, LineTextMessageEvent
from src.domain.line.services import LineMessagingService
from src.infrastructure.logging.error_handler import safe_background_task

router = APIRouter(prefix="/api/v1/webhook", tags=["webhook"])


def _parse_text_events(body_text: str) -> list[LineTextMessageEvent]:
    """從 LINE Webhook body 解析文字訊息事件。"""
    data = json.loads(body_text)
    events: list[LineTextMessageEvent] = []
    for event_data in data.get("events", []):
        if (
            event_data.get("type") == "message"
            and event_data.get("message", {}).get("type") == "text"
        ):
            events.append(
                LineTextMessageEvent(
                    reply_token=event_data["replyToken"],
                    user_id=event_data["source"]["userId"],
                    message_text=event_data["message"]["text"],
                    timestamp=event_data["timestamp"],
                )
            )
    return events


def _parse_postback_events(body_text: str) -> list[LinePostbackEvent]:
    """從 LINE Webhook body 解析 postback 事件。"""
    data = json.loads(body_text)
    events: list[LinePostbackEvent] = []
    for event_data in data.get("events", []):
        if event_data.get("type") == "postback":
            events.append(
                LinePostbackEvent(
                    reply_token=event_data["replyToken"],
                    user_id=event_data["source"]["userId"],
                    postback_data=event_data["postback"]["data"],
                    timestamp=event_data["timestamp"],
                )
            )
    return events


@router.post("/line")
@inject
async def line_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str = Header(...),
    line_service: LineMessagingService = Depends(
        Provide[Container.line_messaging_service]
    ),
    use_case: HandleWebhookUseCase = Depends(
        Provide[Container.handle_webhook_use_case]
    ),
) -> dict:
    body = await request.body()
    body_text = body.decode("utf-8")

    if not await line_service.verify_signature(body_text, x_line_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    events = _parse_text_events(body_text)
    postback_events = _parse_postback_events(body_text)

    if events:
        background_tasks.add_task(
            safe_background_task,
            use_case.execute, events,
            task_name="handle_webhook",
        )

    for pb_event in postback_events:
        background_tasks.add_task(
            safe_background_task,
            use_case.handle_postback, pb_event, "",
            task_name="handle_postback",
        )

    return {"status": "ok"}


@router.post("/line/{bot_id}")
@inject
async def line_webhook_multitenant(
    bot_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str = Header(...),
    use_case: HandleWebhookUseCase = Depends(
        Provide[Container.handle_webhook_use_case]
    ),
) -> dict:
    body = await request.body()
    body_text = body.decode("utf-8")

    # E5: 不在 router 解析事件，交由 Use Case 先驗簽再 parse
    background_tasks.add_task(
        safe_background_task,
        use_case.execute_for_bot, bot_id, body_text, x_line_signature,
        task_name="execute_for_bot",
        bot_id=bot_id,
    )

    return {"status": "ok"}
