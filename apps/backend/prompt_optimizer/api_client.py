from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    answer: str
    conversation_id: str
    tool_calls: list[dict[str, str]]  # [{tool_name, reasoning}]
    sources: list[dict[str, Any]]  # [{document_name, content_snippet, score}]
    usage: dict[str, Any] | None = (
        None  # {model, input_tokens, output_tokens, total_tokens, estimated_cost}
    )
    latency_ms: int = 0


class AgentAPIClient:
    def __init__(
        self,
        base_url: str,
        jwt_token: str,
        refresh_token: str = "",
        timeout: int = 60,
    ):
        self._base_url = base_url
        self._refresh_token = refresh_token
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Content-Type": "application/json",
            },
        )

    async def _refresh_access_token(self) -> bool:
        """Exchange refresh token for a new access token (same as frontend)."""
        if not self._refresh_token:
            return False
        try:
            resp = await self._client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": self._refresh_token},
            )
            if resp.status_code != 200:
                logger.warning("Token refresh failed: %d", resp.status_code)
                return False
            data = resp.json()
            new_access = data["access_token"]
            self._refresh_token = data.get("refresh_token", self._refresh_token)
            self._client.headers["Authorization"] = f"Bearer {new_access}"
            logger.info("Access token refreshed successfully")
            return True
        except Exception as e:
            logger.warning("Token refresh error: %s", e)
            return False

    async def chat(
        self,
        message: str,
        bot_id: str | None = None,
        knowledge_base_id: str | None = None,
        conversation_id: str | None = None,
    ) -> ChatResult:
        payload: dict[str, Any] = {"message": message}
        if bot_id:
            payload["bot_id"] = bot_id
        if knowledge_base_id:
            payload["knowledge_base_id"] = knowledge_base_id
        if conversation_id:
            payload["conversation_id"] = conversation_id

        start = time.monotonic()
        resp = await self._client.post("/api/v1/agent/chat", json=payload)

        # Auto-refresh on 401 (same behavior as frontend)
        if resp.status_code == 401:
            refreshed = await self._refresh_access_token()
            if refreshed:
                start = time.monotonic()
                resp = await self._client.post(
                    "/api/v1/agent/chat", json=payload
                )

        latency_ms = int((time.monotonic() - start) * 1000)
        resp.raise_for_status()
        data = resp.json()

        return ChatResult(
            answer=data["answer"],
            conversation_id=data["conversation_id"],
            tool_calls=data.get("tool_calls", []),
            sources=data.get("sources", []),
            usage=data.get("usage"),
            latency_ms=latency_ms,
        )

    async def close(self):
        await self._client.aclose()
