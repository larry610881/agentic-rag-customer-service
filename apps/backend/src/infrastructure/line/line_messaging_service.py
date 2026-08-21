"""LINE Messaging API 實作"""

import base64
import hashlib
import hmac

import httpx

from src.domain.line.services import LineMessagingService
from src.infrastructure.logging.setup import get_logger

logger = get_logger(__name__)

# L7：module 級共用 AsyncClient。multitenant factory 每個 webhook 建新 service
# 實例，若每實例各建 AsyncClient 且全 codebase 無 aclose() → 每請求遺留未關閉
# 連線/socket 靠 GC 非確定性回收。token 走 per-request header，共用連線池安全。
_shared_client = httpx.AsyncClient(timeout=30.0)


class HttpxLineMessagingService(LineMessagingService):
    def __init__(self, channel_secret: str, channel_access_token: str):
        self._channel_secret = channel_secret
        self._channel_access_token = channel_access_token
        self._client = _shared_client

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
        self, reply_token: str, text: str, message_id: str,
        extra_messages: list[dict] | None = None,
    ) -> None:
        messages: list[dict] = []

        # Add flex messages first (cards before text looks better)
        if extra_messages:
            messages.extend(extra_messages[:4])  # Reserve 1 slot for text

        # Text message with quick reply (always last)
        messages.append({
            "type": "text",
            "text": text,
            "quickReply": self._feedback_quick_reply(message_id),
        })

        resp = await self._client.post(
            "https://api.line.me/v2/bot/message/reply",
            headers=self._auth_headers(),
            json={
                "replyToken": reply_token,
                "messages": messages[:5],  # LINE max 5 messages per reply
            },
        )
        # reply 失敗（400 空文字 / 無效 token、429 配額、5xx）過去完全靜默，
        # 使用者只看到「沒回應」而 log 顯示 200 → 補 warning 讓失敗可觀測
        status = getattr(resp, "status_code", None)
        if isinstance(status, int) and status >= 400:
            logger.warning(
                "line.reply.failed",
                status_code=status,
                body=(getattr(resp, "text", "") or "")[:200],
                message_types=[m.get("type") for m in messages[:5]],
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

    async def push_flex(
        self, user_id: str, alt_text: str, flex_content: dict
    ) -> None:
        resp = await self._client.post(
            "https://api.line.me/v2/bot/message/push",
            headers=self._auth_headers(),
            json={
                "to": user_id,
                "messages": [
                    {
                        "type": "flex",
                        "altText": alt_text,
                        "contents": flex_content,
                    }
                ],
            },
        )
        if resp.status_code >= 400:
            logger.warning(
                "line.push_flex.failed",
                user_id=user_id,
                status_code=resp.status_code,
                body=resp.text[:200],
            )

    async def show_loading(self, user_id: str, seconds: int = 20) -> None:
        try:
            # 官方端點必須含 /start — 少了會 404，動畫靜默失效
            # （POC 問題 1 UX 回歸：2026-07-17 線上 log 實證 404 Not found）
            resp = await self._client.post(
                "https://api.line.me/v2/bot/chat/loading/start",
                headers=self._auth_headers(),
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
