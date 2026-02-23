"""OpenAILLMService — httpx 直接呼叫 OpenAI Chat Completions API"""

from collections.abc import AsyncIterator

import httpx

from src.domain.rag.services import LLMService


class OpenAILLMService(LLMService):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_tokens: int = 1024,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._base_url = "https://api.openai.com/v1"

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_messages(
        self, system_prompt: str, user_message: str, context: str
    ) -> list[dict]:
        content = (
            f"Context:\n{context}\n\nQuestion: {user_message}"
            if context.strip()
            else user_message
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> str:
        messages = self._build_messages(system_prompt, user_message, context)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers=self._build_headers(),
                json={
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
    ) -> AsyncIterator[str]:
        messages = self._build_messages(system_prompt, user_message, context)
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._build_headers(),
                json={
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "messages": messages,
                    "stream": True,
                },
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
                    delta = event["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
