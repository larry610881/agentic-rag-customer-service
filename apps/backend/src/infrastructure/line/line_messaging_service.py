"""LINE Messaging API 實作"""

import base64
import hashlib
import hmac

import httpx

from src.domain.line.services import LineMessagingService


class HttpxLineMessagingService(LineMessagingService):
    def __init__(self, channel_secret: str, channel_access_token: str):
        self._channel_secret = channel_secret
        self._channel_access_token = channel_access_token

    async def reply_text(self, reply_token: str, text: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.line.me/v2/bot/message/reply",
                headers={
                    "Authorization": f"Bearer {self._channel_access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "replyToken": reply_token,
                    "messages": [{"type": "text", "text": text}],
                },
            )

    async def reply_with_quick_reply(
        self, reply_token: str, text: str, message_id: str
    ) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.line.me/v2/bot/message/reply",
                headers={
                    "Authorization": f"Bearer {self._channel_access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "replyToken": reply_token,
                    "messages": [
                        {
                            "type": "text",
                            "text": text,
                            "quickReply": {
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
                                            "data": (
                                                f"feedback:{message_id}"
                                                ":thumbs_down"
                                            ),
                                            "displayText": "\U0001f44e",
                                        },
                                    },
                                ]
                            },
                        }
                    ],
                },
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
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.line.me/v2/bot/message/reply",
                headers={
                    "Authorization": f"Bearer {self._channel_access_token}",
                    "Content-Type": "application/json",
                },
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
                                            "data": f"feedback_reason:{message_id}:{btn['tag']}",
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

    async def verify_signature(self, body: str, signature: str) -> bool:
        hash_value = hmac.new(
            self._channel_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(hash_value).decode("utf-8")
        return hmac.compare_digest(signature, expected)
