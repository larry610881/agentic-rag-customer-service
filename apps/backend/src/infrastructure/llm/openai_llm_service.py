"""OpenAILLMService — httpx 直接呼叫 OpenAI Chat Completions API"""

import time
from collections.abc import AsyncIterator

import httpx

from src.domain.rag.pricing import calculate_usage
from src.domain.rag.services import LLMService
from src.domain.rag.value_objects import LLMResult
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class OpenAILLMService(LLMService):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_tokens: int = 1024,
        pricing: dict[str, dict[str, float]] | None = None,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._base_url = base_url
        self._pricing = pricing or {}

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
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
    ) -> LLMResult:
        log = logger.bind(model=self._model, base_url=self._base_url)
        log.info("llm.openai.request", api_key_set=bool(self._api_key), api_key_prefix=self._api_key[:8] if self._api_key else "EMPTY")
        start = time.perf_counter()

        messages = self._build_messages(system_prompt, user_message, context)
        body: dict = {
            "model": self._model,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
            "messages": messages,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if frequency_penalty is not None and "googleapis.com" not in self._base_url:
            body["frequency_penalty"] = frequency_penalty
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._build_headers(),
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                usage_data = data.get("usage", {})
                usage = calculate_usage(
                    model=self._model,
                    input_tokens=usage_data.get("prompt_tokens", 0),
                    output_tokens=usage_data.get("completion_tokens", 0),
                    pricing=self._pricing,
                )
                elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                log.info(
                    "llm.openai.done",
                    latency_ms=elapsed_ms,
                    input_tokens=usage_data.get("prompt_tokens", 0),
                    output_tokens=usage_data.get("completion_tokens", 0),
                )
                return LLMResult(text=text, usage=usage)
        except httpx.HTTPStatusError as e:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            log.error(
                "llm.openai.failed",
                latency_ms=elapsed_ms,
                status_code=e.response.status_code,
                response_body=e.response.text[:500],
            )
            raise
        except Exception:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            log.exception("llm.openai.failed", latency_ms=elapsed_ms)
            raise

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
    ) -> AsyncIterator[str]:
        messages = self._build_messages(system_prompt, user_message, context)
        body: dict = {
            "model": self._model,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if frequency_penalty is not None and "googleapis.com" not in self._base_url:
            body["frequency_penalty"] = frequency_penalty
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
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
                    delta = event["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
