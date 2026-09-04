"""Microsoft Teams 通知 — Workflows（Power Automate）webhook + Adaptive Card

舊版 Office 365 Connector「Incoming Webhook」已退場；請在 Teams 用 Workflows 的
「When a Teams webhook request is received」產生 URL。payload 用 Adaptive Card：
``type=message``、``attachments[0].contentType=application/vnd.microsoft.card.adaptive``。
"""

import json
from typing import Any

import httpx
import structlog

from src.domain.observability.notification import (
    NotificationChannel,
    NotificationSender,
)

_logger = structlog.get_logger(__name__)


def build_adaptive_card_message(subject: str, body: str) -> dict[str, Any]:
    """body 每行 ``Key：Value`` 轉成 FactSet；其餘行當 TextBlock。"""
    facts: list[dict[str, str]] = []
    texts: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        for sep in ("：", ": "):
            if sep in line:
                key, value = line.split(sep, 1)
                if key and len(key) <= 20:
                    facts.append({"title": key.strip(), "value": value.strip()})
                    break
        else:
            texts.append(line)
    card_body: list[dict[str, Any]] = [
        {"type": "TextBlock", "text": subject, "weight": "Bolder", "size": "Medium",
         "wrap": True},
    ]
    if facts:
        card_body.append({"type": "FactSet", "facts": facts})
    for text in texts:
        card_body.append({"type": "TextBlock", "text": text, "wrap": True})
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": card_body,
            },
        }],
    }


class TeamsWorkflowSender(NotificationSender):
    def __init__(
        self, timeout_seconds: float = 10.0, transport: Any | None = None
    ) -> None:
        self._timeout = timeout_seconds
        self._transport = transport  # 測試注入 httpx.MockTransport

    def channel_type(self) -> str:
        return "teams"

    async def send(
        self, channel: NotificationChannel, subject: str, body: str
    ) -> None:
        try:
            config = json.loads(channel.config_encrypted)
        except (json.JSONDecodeError, TypeError):
            config = {}
        url = (config.get("webhook_url") or "").strip()
        if not url:
            _logger.warning("teams_sender.not_configured", channel_id=channel.id)
            return
        payload = build_adaptive_card_message(subject, body)
        async with httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport
        ) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 300:
                _logger.warning(
                    "teams_sender.rejected", channel_id=channel.id,
                    status=resp.status_code,
                )
