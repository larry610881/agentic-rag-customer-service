"""Lightweight LLM caller — resolves provider:model and calls the right SDK.

Used by services that need simple LLM calls (context enrichment, guard, classification)
without going through the full DynamicLLMFactory/AgentService pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Awaitable

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

# Provider → default base_url mapping (same as dynamic_llm_factory)
_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openrouter": "https://openrouter.ai/api/v1",
    "litellm": "https://litellm-server.pic-ai.work",
}


@dataclass
class LLMCallResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


async def call_llm(
    model_spec: str,
    prompt: str,
    max_tokens: int = 200,
    api_key_resolver: Callable[[str], Awaitable[str]] | None = None,
) -> LLMCallResult:
    """Call LLM with provider:model format.

    Args:
        model_spec: "provider:model_id" (e.g. "anthropic:claude-haiku-4-5")
                    or just "model_id" (defaults to anthropic)
        prompt: user message
        max_tokens: max output tokens
        api_key_resolver: async callable(provider_name) -> api_key

    Returns:
        LLMCallResult with text and token counts
    """
    provider, model = _parse_model_spec(model_spec)
    api_key = ""
    if api_key_resolver:
        api_key = await api_key_resolver(provider)
    if not api_key:
        raise RuntimeError(f"No API key for provider '{provider}'")

    if provider == "anthropic":
        return await _call_anthropic(api_key, model, prompt, max_tokens)
    else:
        base_url = _BASE_URLS.get(provider, "")
        return await _call_openai_compatible(api_key, model, prompt, max_tokens, base_url)


def _parse_model_spec(model_spec: str) -> tuple[str, str]:
    """Parse 'provider:model_id' → (provider, model_id)."""
    if ":" in model_spec:
        provider, model = model_spec.split(":", 1)
        return provider, model
    # No prefix → assume anthropic
    return "anthropic", model_spec


async def _call_anthropic(
    api_key: str, model: str, prompt: str, max_tokens: int
) -> LLMCallResult:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=api_key)
    resp = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return LLMCallResult(
        text=resp.content[0].text.strip(),
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
        model=model,
    )


async def _call_openai_compatible(
    api_key: str, model: str, prompt: str, max_tokens: int, base_url: str
) -> LLMCallResult:
    import httpx
    url = f"{base_url}/chat/completions"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage", {})
        return LLMCallResult(
            text=text,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=model,
        )
