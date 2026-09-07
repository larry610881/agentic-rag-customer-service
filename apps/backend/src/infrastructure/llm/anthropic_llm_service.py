"""AnthropicLLMService — httpx 直接呼叫 Anthropic Messages API"""

import time
from collections.abc import AsyncIterator

import httpx

from src.domain.rag.pricing import calculate_usage
from src.domain.rag.services import LLMService
from src.domain.rag.value_objects import LLMResult
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


# === Issue #72：推理強度 → Anthropic thinking / output_config.effort 對應 ======
#
# 依 claude-api skill（Thinking & Effort 快速參考）：
# - Opus 4.6 / Sonnet 4.6 起支援 adaptive thinking（{"type": "adaptive"}）與
#   output_config.effort；更舊的模型（3.x / 4 / 4.1 / 4.5 / Haiku 4.5）送
#   adaptive 或 effort 會被 API 拒絕 → 一律丟棄（維持供應商預設）。
# - Opus 5 / Sonnet 5 省略 thinking 時**預設就會思考**，關閉須明確送
#   {"type": "disabled"}（effort ≤ high 時合法；本專案最高只送 high）。
# - Opus 4.8 / 4.7 / 4.6 與更舊模型省略 thinking = 不思考 → none 時不帶參數即可。
# - Fable 5 / Mythos 5 系列 thinking 永遠開啟，disabled 回 400 → none 無法生效，丟棄。
_ANTHROPIC_ADAPTIVE_PREFIXES = (
    "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8", "claude-opus-5",
    "claude-sonnet-4-6", "claude-sonnet-5",
    "claude-fable-5", "claude-mythos-5",
)
_ANTHROPIC_THINKING_DEFAULT_ON_PREFIXES = ("claude-opus-5", "claude-sonnet-5")
_ANTHROPIC_THINKING_ALWAYS_ON_PREFIXES = ("claude-fable-5", "claude-mythos-5")
_ANTHROPIC_EFFORTS = ("low", "medium", "high")


def _has_prefix(model: str, prefixes: tuple[str, ...]) -> bool:
    return any(model.startswith(p) for p in prefixes)


def anthropic_thinking_config(
    model: str, reasoning_effort: str | None
) -> tuple[dict | None, str | None, str | None]:
    """把 bot 的 reasoning_effort 對應成 Anthropic 參數。

    回傳 (thinking, output_effort, effective)：
    - thinking：Messages API `thinking` 物件（None = 不帶）
    - output_effort：`output_config.effort` 值（None = 不帶）
    - effective：實際生效值（"none" / "low" / "medium" / "high"；None = 丟棄，
      維持供應商預設）。呼叫端據此記 trace 與 `llm.reasoning_effort.dropped`。
    """
    if not reasoning_effort:
        return None, None, None
    if reasoning_effort == "none":
        if _has_prefix(model, _ANTHROPIC_THINKING_ALWAYS_ON_PREFIXES):
            return None, None, None  # 無法關閉
        if _has_prefix(model, _ANTHROPIC_THINKING_DEFAULT_ON_PREFIXES):
            return {"type": "disabled"}, None, "none"
        return None, None, "none"  # 省略 = 不思考
    if reasoning_effort in _ANTHROPIC_EFFORTS and _has_prefix(
        model, _ANTHROPIC_ADAPTIVE_PREFIXES
    ):
        return {"type": "adaptive"}, reasoning_effort, reasoning_effort
    return None, None, None


def anthropic_chat_model_kwargs(
    model: str, reasoning_effort: str | None
) -> dict:
    """langchain_anthropic.ChatAnthropic 建構參數（thinking / reasoning_effort）。

    ChatAnthropic 1.7：`thinking` 直傳 Messages API；`reasoning_effort`
    （alias effort）寫入 `output_config.effort`。丟棄時記 log。
    """
    thinking, effort, effective = anthropic_thinking_config(model, reasoning_effort)
    if reasoning_effort and effective is None:
        logger.warning(
            "llm.reasoning_effort.dropped",
            model=model,
            requested=reasoning_effort,
            provider="anthropic",
        )
    kwargs: dict = {}
    if thinking is not None:
        kwargs["thinking"] = thinking
    if effort is not None:
        kwargs["reasoning_effort"] = effort
    return kwargs


def anthropic_output_config(response_schema: dict | None) -> dict | None:
    """Issue #70：Messages API 原生結構化輸出 ``output_config.format``
    （json_schema；Claude 4.5+ 支援，見 domain/llm/structured_output 能力表）。
    json_object 級（舊模型）無對應參數 → 走 prompt 約束 + 系統驗證。"""
    if not response_schema:
        return None
    return {"format": {"type": "json_schema", "schema": response_schema}}


def _first_text_block(content: list) -> str:
    for block in content:
        if isinstance(block, dict) and block.get("type", "text") == "text":
            return str(block.get("text", ""))
    return ""


class AnthropicLLMService(LLMService):
    @property
    def model_name(self) -> str:
        return self._model

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

    def get_chat_model(
        self,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
        response_schema: dict | None = None,
        response_json_object: bool = False,
    ):
        """Return a LangChain ChatModel using the same API key.

        Issue #72：reasoning_effort 對應 thinking / output_config.effort
        （anthropic_thinking_config）；不合法的組合丟棄並記
        `llm.reasoning_effort.dropped`。
        response_json_object（B 級）無原生參數，忽略（prompt 約束 + 驗證）。
        """
        from langchain_anthropic import ChatAnthropic

        kwargs: dict = {
            "model": self._model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": self._api_key,
        }
        kwargs.update(anthropic_chat_model_kwargs(self._model, reasoning_effort))
        output_config = anthropic_output_config(response_schema)
        if output_config is not None:
            kwargs["output_config"] = output_config  # langchain-anthropic ≥ 1.x
        return ChatAnthropic(**kwargs)

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
        response_schema: dict | None = None,
        reasoning_effort: str | None = None,
    ) -> dict:
        content = (
            f"Context:\n{context}\n\nQuestion: {user_message}"
            if context.strip()
            else user_message
        )
        # Use structured system block with cache_control for prompt caching
        body: dict = {
            "model": self._model,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [{"role": "user", "content": content}],
        }
        if temperature is not None:
            body["temperature"] = temperature
        output_config = anthropic_output_config(response_schema)
        if output_config is not None:
            body["output_config"] = output_config  # Issue #70：原生結構化輸出
        # Issue #72：推理強度 → thinking / output_config.effort
        thinking, effort, effective = anthropic_thinking_config(
            self._model, reasoning_effort
        )
        if reasoning_effort and effective is None:
            logger.warning(
                "llm.reasoning_effort.dropped",
                model=self._model,
                requested=reasoning_effort,
                provider="anthropic",
            )
        if thinking is not None:
            body["thinking"] = thinking
        if effort is not None:
            body.setdefault("output_config", {})["effort"] = effort
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
        reasoning_effort: str | None = None,
    ) -> LLMResult:
        # Anthropic API does not support frequency_penalty (OpenAI-only hint) — ignored.
        # Issue #72：reasoning_effort 對應 thinking / effort（_build_body）
        log = logger.bind(model=self._model)
        log.debug("llm.anthropic.request")
        start = time.perf_counter()

        body = self._build_body(
            system_prompt, user_message, context,
            temperature=temperature, max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
        )
        try:
            resp = await self._client.post(
                f"{self._base_url}/messages",
                headers=self._build_headers(),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            # Issue #72：thinking 開啟時 content[0] 可能是 thinking 區塊 → 取第一個 text
            text = _first_text_block(data.get("content") or [])
            usage_data = data.get("usage", {})
            cache_read = usage_data.get("cache_read_input_tokens", 0)
            cache_creation = usage_data.get("cache_creation_input_tokens", 0)
            usage = calculate_usage(
                model=self._model,
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                pricing=self._pricing,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
            )
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            log.info(
                "llm.anthropic.done",
                latency_ms=elapsed_ms,
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
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
        cache_read_tokens = 0
        cache_creation_tokens = 0
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
                        cache_read_tokens = u.get("cache_read_input_tokens", 0)
                        cache_creation_tokens = u.get("cache_creation_input_tokens", 0)
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
        if usage_collector is not None and (input_tokens or output_tokens or cache_read_tokens):
            usage = calculate_usage(
                model=self._model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                pricing=self._pricing,
                cache_read_tokens=cache_read_tokens,
                cache_creation_tokens=cache_creation_tokens,
            )
            usage_collector["model"] = usage.model
            usage_collector["input_tokens"] = usage.input_tokens
            usage_collector["output_tokens"] = usage.output_tokens
            usage_collector["total_tokens"] = usage.total_tokens
            usage_collector["estimated_cost"] = usage.estimated_cost
            usage_collector["cache_read_tokens"] = usage.cache_read_tokens
            usage_collector["cache_creation_tokens"] = usage.cache_creation_tokens
