"""AnthropicLLMService — httpx 直接呼叫 Anthropic Messages API"""

import time
from collections.abc import AsyncIterator

import httpx

from src.domain.rag.pricing import calculate_usage
from src.domain.rag.services import LLMService
from src.domain.rag.value_objects import LLMResult
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class AnthropicLLMService(LLMService):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
        pricing: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._base_url = "https://api.anthropic.com/v1"
        self._pricing = pricing or {}
        self._client = httpx.AsyncClient(timeout=60.0)

    def _build_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _build_body(
        self,
        system_prompt: str,
        user_message: str,
        context: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        content = (
            f"Context:\n{context}\n\nQuestion: {user_message}"
            if context.strip()
            else user_message
        )
        body: dict = {
            "model": self._model,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": content}],
        }
        if temperature is not None:
            body["temperature"] = temperature
        return body

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
        # Anthropic API does not support frequency_penalty — ignored
        log = logger.bind(model=self._model)
        log.debug("llm.anthropic.request")
        start = time.perf_counter()

        body = self._build_body(
            system_prompt, user_message, context,
            temperature=temperature, max_tokens=max_tokens,
        )
        try:
            resp = await self._client.post(
                f"{self._base_url}/messages",
                headers=self._build_headers(),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]
            usage_data = data.get("usage", {})
            usage = calculate_usage(
                model=self._model,
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                pricing=self._pricing,
            )
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            log.info(
                "llm.anthropic.done",
                latency_ms=elapsed_ms,
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
            )
            return LLMResult(text=text, usage=usage)
        except Exception:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            log.exception("llm.anthropic.failed", latency_ms=elapsed_ms)
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
        usage_collector: dict | None = None,
    ) -> AsyncIterator[str]:
        import json as json_mod

        body = self._build_body(
            system_prompt, user_message, context,
            temperature=temperature, max_tokens=max_tokens,
        )
        body["stream"] = True
        input_tokens = 0
        output_tokens = 0
        async with self._client.stream(
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
                    event = json_mod.loads(payload)
                    # Capture usage from message_start
                    if event.get("type") == "message_start":
                        msg = event.get("message", {})
                        u = msg.get("usage", {})
                        input_tokens = u.get("input_tokens", 0)
                    # Capture usage from message_delta
                    elif event.get("type") == "message_delta":
                        u = event.get("usage", {})
                        output_tokens = u.get("output_tokens", 0)
                    elif event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        text = delta.get("text", "")
                        if text:
                            yield text
        # Write final usage to collector
        if usage_collector is not None and (input_tokens or output_tokens):
            usage = calculate_usage(
                model=self._model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                pricing=self._pricing,
            )
            usage_collector["model"] = usage.model
            usage_collector["input_tokens"] = usage.input_tokens
            usage_collector["output_tokens"] = usage.output_tokens
            usage_collector["total_tokens"] = usage.total_tokens
            usage_collector["estimated_cost"] = usage.estimated_cost
