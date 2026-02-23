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

    async def verify_signature(self, body: str, signature: str) -> bool:
        hash_value = hmac.new(
            self._channel_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(hash_value).decode("utf-8")
        return hmac.compare_digest(signature, expected)
