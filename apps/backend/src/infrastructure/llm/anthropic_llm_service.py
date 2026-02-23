"""AnthropicLLMService — httpx 直接呼叫 Anthropic Messages API"""

from collections.abc import AsyncIterator

import httpx

from src.domain.rag.services import LLMService


class AnthropicLLMService(LLMService):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._base_url = "https://api.anthropic.com/v1"

    def _build_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _build_body(
        self, system_prompt: str, user_message: str, context: str
    ) -> dict:
        content = (
            f"Context:\n{context}\n\nQuestion: {user_message}"
            if context.strip()
            else user_message
        )
        return {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": content}],
        }

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> str:
        body = self._build_body(system_prompt, user_message, context)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base_url}/messages",
                headers=self._build_headers(),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> AsyncIterator[str]:
        body = self._build_body(system_prompt, user_message, context)
        body["stream"] = True
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/messages",
                headers=self._build_headers(),
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        break
                    import json

                    event = json.loads(payload)
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        text = delta.get("text", "")
                        if text:
                            yield text
