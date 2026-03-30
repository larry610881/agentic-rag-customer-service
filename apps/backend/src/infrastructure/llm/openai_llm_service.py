"""OpenAILLMService — httpx 直接呼叫 OpenAI Chat Completions API"""

import time
from collections.abc import AsyncIterator

import httpx

from src.domain.rag.pricing import calculate_usage
from src.domain.rag.services import LLMService
from src.domain.rag.value_objects import LLMResult
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


# Models that require max_completion_tokens instead of max_tokens
_NEW_PARAM_PREFIXES = ("o1", "o3", "gpt-5")


def _needs_max_completion_tokens(model: str) -> bool:
    return any(model.startswith(p) for p in _NEW_PARAM_PREFIXES)


class OpenAILLMService(LLMService):
    @property
    def model_name(self) -> str:
        return self._model

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
        self._client = httpx.AsyncClient(timeout=60.0)

    def get_chat_model(
        self,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ):
        """Return a LangChain ChatModel using the same API key and base_url."""
        from langchain_openai import ChatOpenAI

        kwargs: dict = {
            "model": self._model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": self._api_key,
        }
        if self._base_url and self._base_url != "https://api.openai.com/v1":
            kwargs["base_url"] = self._base_url
        return ChatOpenAI(**kwargs)

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
        key_prefix = self._api_key[:8] if self._api_key else "EMPTY"
        log.info(
            "llm.openai.request",
            api_key_set=bool(self._api_key),
            api_key_prefix=key_prefix,
        )
        start = time.perf_counter()

        messages = self._build_messages(system_prompt, user_message, context)
        resolved_max = max_tokens if max_tokens is not None else self._max_tokens
        tok_key = (
            "max_completion_tokens"
            if _needs_max_completion_tokens(self._model)
            else "max_tokens"
        )
        body: dict = {
            "model": self._model,
            tok_key: resolved_max,
            "messages": messages,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if frequency_penalty is not None and "googleapis.com" not in self._base_url:
            body["frequency_penalty"] = frequency_penalty
        try:
            resp = await self._client.post(
                f"{self._base_url}/chat/completions",
                headers=self._build_headers(),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            usage_data = data.get("usage", {})

            # Extract cache tokens (DeepSeek vs OpenAI)
            ds_hit = usage_data.get("prompt_cache_hit_tokens", 0)
            ds_miss = usage_data.get("prompt_cache_miss_tokens", 0)
            if ds_hit or ds_miss:
                input_tokens = ds_miss
                cache_read = ds_hit
            else:
                prompt_details = usage_data.get("prompt_tokens_details") or {}
                cached = prompt_details.get("cached_tokens", 0)
                raw_input = usage_data.get("prompt_tokens", 0)
                cache_read = cached
                input_tokens = raw_input - cache_read

            usage = calculate_usage(
                model=self._model,
                input_tokens=input_tokens,
                output_tokens=usage_data.get("completion_tokens", 0),
                pricing=self._pricing,
                cache_read_tokens=cache_read,
            )
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            log.info(
                "llm.openai.done",
                latency_ms=elapsed_ms,
                input_tokens=input_tokens,
                output_tokens=usage_data.get("completion_tokens", 0),
                cache_read_tokens=cache_read,
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
        usage_collector: dict | None = None,
    ) -> AsyncIterator[str]:
        import json as json_mod

        start = time.perf_counter()
        messages = self._build_messages(system_prompt, user_message, context)
        resolved_max = max_tokens if max_tokens is not None else self._max_tokens
        tok_key = (
            "max_completion_tokens"
            if _needs_max_completion_tokens(self._model)
            else "max_tokens"
        )
        body: dict = {
            "model": self._model,
            tok_key: resolved_max,
            "messages": messages,
            "stream": True,
        }
        if usage_collector is not None:
            body["stream_options"] = {"include_usage": True}
        if temperature is not None:
            body["temperature"] = temperature
        if frequency_penalty is not None and "googleapis.com" not in self._base_url:
            body["frequency_penalty"] = frequency_penalty
        async with self._client.stream(
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
                    event = json_mod.loads(payload)
                    # Capture usage from final chunk (stream_options)
                    if usage_collector is not None and event.get("usage"):
                        u = event["usage"]
                        # Extract cache tokens (DeepSeek vs OpenAI)
                        _ds_hit = u.get("prompt_cache_hit_tokens", 0)
                        _ds_miss = u.get("prompt_cache_miss_tokens", 0)
                        if _ds_hit or _ds_miss:
                            _inp = _ds_miss
                            _cr = _ds_hit
                        else:
                            _details = u.get("prompt_tokens_details") or {}
                            _cached = _details.get("cached_tokens", 0)
                            _raw = u.get("prompt_tokens", 0)
                            _cr = _cached
                            _inp = _raw - _cr
                        usage = calculate_usage(
                            model=self._model,
                            input_tokens=_inp,
                            output_tokens=u.get("completion_tokens", 0),
                            pricing=self._pricing,
                            cache_read_tokens=_cr,
                        )
                        usage_collector["model"] = usage.model
                        usage_collector["input_tokens"] = usage.input_tokens
                        usage_collector["output_tokens"] = usage.output_tokens
                        usage_collector["total_tokens"] = usage.total_tokens
                        usage_collector["estimated_cost"] = usage.estimated_cost
                        usage_collector["cache_read_tokens"] = usage.cache_read_tokens
                        usage_collector["cache_creation_tokens"] = usage.cache_creation_tokens
                        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                        logger.info(
                            "llm.openai.stream.done",
                            model=self._model,
                            latency_ms=elapsed_ms,
                            input_tokens=usage.input_tokens,
                            output_tokens=usage.output_tokens,
                        )
                    choices = event.get("choices", [])
                    delta = choices[0].get("delta", {}) if choices else {}
                    content = delta.get("content", "")
                    if content:
                        yield content
