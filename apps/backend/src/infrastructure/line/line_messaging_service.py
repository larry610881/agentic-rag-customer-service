"""LINE Messaging API 實作"""

import base64
import hashlib
import hmac

import httpx

from src.domain.line.services import LineMessagingService
from src.infrastructure.logging.setup import get_logger

logger = get_logger(__name__)


class HttpxLineMessagingService(LineMessagingService):
    def __init__(self, channel_secret: str, channel_access_token: str):
        self._channel_secret = channel_secret
        self._channel_access_token = channel_access_token
        self._client = httpx.AsyncClient(timeout=30.0)

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._channel_access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _feedback_quick_reply(message_id: str) -> dict:
        return {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": "\U0001f44d \u6709\u5e6b\u52a9",
                        "data": f"feedback:{message_id}:thumbs_up",
                        "displayText": "\U0001f44d",
                    },
                },
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": "\U0001f44e \u6c92\u5e6b\u52a9",
                        "data": f"feedback:{message_id}:thumbs_down",
                        "displayText": "\U0001f44e",
                    },
                },
            ]
        }

    async def reply_text(self, reply_token: str, text: str) -> None:
        await self._client.post(
            "https://api.line.me/v2/bot/message/reply",
            headers=self._auth_headers(),
            json={
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": text}],
            },
        )

    async def reply_with_quick_reply(
        self, reply_token: str, text: str, message_id: str
    ) -> None:
        await self._client.post(
            "https://api.line.me/v2/bot/message/reply",
            headers=self._auth_headers(),
            json={
                "replyToken": reply_token,
                "messages": [
                    {
                        "type": "text",
                        "text": text,
                        "quickReply": self._feedback_quick_reply(message_id),
                    }
                ],
            },
        )

    async def push_with_quick_reply(
        self, user_id: str, text: str, message_id: str
    ) -> None:
        resp = await self._client.post(
            "https://api.line.me/v2/bot/message/push",
            headers=self._auth_headers(),
            json={
                "to": user_id,
                "messages": [
                    {
                        "type": "text",
                        "text": text,
                        "quickReply": self._feedback_quick_reply(message_id),
                    }
                ],
            },
        )
        if resp.status_code >= 400:
                logger.warning(
                    "line.push.failed",
                    user_id=user_id,
                    status_code=resp.status_code,
                    body=resp.text[:200],
                )

    async def reply_with_reason_options(
        self, reply_token: str, message_id: str
    ) -> None:
        buttons = [
            {"tag": "incorrect", "label": "答案不正確"},
            {"tag": "incomplete", "label": "答案不完整"},
            {"tag": "irrelevant", "label": "沒回答我的問題"},
            {"tag": "tone", "label": "語氣/格式不好"},
        ]
        await self._client.post(
            "https://api.line.me/v2/bot/message/reply",
            headers=self._auth_headers(),
            json={
                "replyToken": reply_token,
                "messages": [
                    {
                        "type": "text",
                        "text": "請問哪裡需要改進？",
                        "quickReply": {
                            "items": [
                                {
                                    "type": "action",
                                    "action": {
                                        "type": "postback",
                                        "label": btn["label"],
                                        "data": (
                                            f"feedback_reason:"
                                            f"{message_id}:"
                                            f"{btn['tag']}"
                                        ),
                                        "displayText": btn["label"],
                                    },
                                }
                                for btn in buttons
                            ]
                        },
                    }
                ],
            },
        )

    async def show_loading(self, user_id: str, seconds: int = 20) -> None:
        try:
            resp = await self._client.post(
                "https://api.line.me/v2/bot/chat/loading",
                headers={
                    "Authorization": f"Bearer {self._channel_access_token}",
                    "Content-Type": "application/json",
                },
                json={"chatId": user_id, "loadingSeconds": seconds},
            )
            logger.info(
                "line.show_loading",
                user_id=user_id,
                status_code=resp.status_code,
            )
            if resp.status_code >= 400:
                logger.warning(
                    "line.show_loading.failed",
                    user_id=user_id,
                    status_code=resp.status_code,
                    body=resp.text[:200],
                )
        except Exception:
            logger.exception("line.show_loading.error", user_id=user_id)

    async def verify_signature(self, body: str, signature: str) -> bool:
        hash_value = hmac.new(
            self._channel_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(hash_value).decode("utf-8")
        return hmac.compare_digest(signature, expected)
