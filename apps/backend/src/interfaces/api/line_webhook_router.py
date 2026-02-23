"""LINE Webhook API 端點"""

import json

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.container import Container
from src.domain.line.entity import LineTextMessageEvent
from src.domain.line.services import LineMessagingService

router = APIRouter(prefix="/api/v1/webhook", tags=["webhook"])


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

    if events:
        background_tasks.add_task(use_case.execute, events)

    return {"status": "ok"}
