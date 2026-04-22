"""Lightweight LLM caller — resolves provider:model and calls the right SDK.

Used by services that need simple LLM calls (context enrichment, guard, classification)
without going through the full DynamicLLMFactory/AgentService pipeline.

S-LLM-Cache.1 更新：
- `prompt` 接受 `str` (backward compat) 或 `list[PromptBlock]`
- `LLMCallResult` 新增 `cache_read_tokens` / `cache_creation_tokens` 欄位
- Anthropic adapter 支援 `cache_control: ephemeral` marker
- OpenAI-compatible adapter 解析 `prompt_tokens_details.cached_tokens`
  （DeepSeek 走 `prompt_cache_hit_tokens` 特殊欄位）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from src.domain.llm import BlockRole, CacheHint, PromptBlock
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
    # S-LLM-Cache.1: cache-aware token tracking
    # - cache_read_tokens: 本次 call 命中 cache 的 input token 數（不計或計折扣）
    # - cache_creation_tokens: 本次 call 寫入 cache 的 input token 數（首次建立 cache）
    # Provider 不支援 cache 時永遠為 0。
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    model: str = ""


def _normalize_blocks(prompt: str | list[PromptBlock]) -> list[PromptBlock]:
    """Backward compat：flat string → 單一 user block，其餘原樣回傳。"""
    if isinstance(prompt, str):
        return [PromptBlock(text=prompt, role=BlockRole.USER, cache=CacheHint.NONE)]
    return list(prompt)


async def call_llm(
    model_spec: str,
    prompt: str | list[PromptBlock],
    max_tokens: int = 200,
    api_key_resolver: Callable[[str], Awaitable[str]] | None = None,
) -> LLMCallResult:
    """Call LLM with provider:model format.

    Args:
        model_spec: "provider:model_id" (e.g. "anthropic:claude-haiku-4-5")
                    or just "model_id" (defaults to anthropic)
        prompt: user message — 可傳 flat string (向後相容) 或
                list[PromptBlock] (S-LLM-Cache.1 結構化 + cache hint)
        max_tokens: max output tokens
        api_key_resolver: async callable(provider_name) -> api_key

    Returns:
        LLMCallResult with text and token counts (including cache breakdown)
    """
    provider, model = _parse_model_spec(model_spec)
    api_key = ""
    if api_key_resolver:
        api_key = await api_key_resolver(provider)
    if not api_key:
        raise RuntimeError(f"No API key for provider '{provider}'")

    blocks = _normalize_blocks(prompt)

    if provider == "anthropic":
        return await _call_anthropic(api_key, model, blocks, max_tokens)
    else:
        base_url = _BASE_URLS.get(provider, "")
        return await _call_openai_compatible(
            api_key, model, blocks, max_tokens, base_url, provider
        )


def _parse_model_spec(model_spec: str) -> tuple[str, str]:
    """Parse 'provider:model_id' → (provider, model_id)."""
    if ":" in model_spec:
        provider, model = model_spec.split(":", 1)
        return provider, model
    # No prefix → assume anthropic
    return "anthropic", model_spec


def _to_anthropic_content(block: PromptBlock) -> dict[str, Any]:
    """Translate a PromptBlock into Anthropic API content element.

    - cache=EPHEMERAL → 加 cache_control marker
    - cache=NONE → 純 text
    """
    item: dict[str, Any] = {"type": "text", "text": block.text}
    if block.cache == CacheHint.EPHEMERAL:
        item["cache_control"] = {"type": "ephemeral"}
    return item


async def _call_anthropic(
    api_key: str,
    model: str,
    blocks: list[PromptBlock],
    max_tokens: int,
) -> LLMCallResult:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)

    # 依 role 拆成 system 陣列 + user content 陣列
    system_blocks = [b for b in blocks if b.role == BlockRole.SYSTEM]
    user_blocks = [b for b in blocks if b.role == BlockRole.USER]

    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
    }
    if system_blocks:
        body["system"] = [_to_anthropic_content(b) for b in system_blocks]

    # user 訊息組合
    if len(user_blocks) == 1 and user_blocks[0].cache == CacheHint.NONE:
        # 單一純文字 → 傳 string 最精簡（與舊 flat-string 行為一致）
        body["messages"] = [{"role": "user", "content": user_blocks[0].text}]
    else:
        body["messages"] = [
            {
                "role": "user",
                "content": [_to_anthropic_content(b) for b in user_blocks],
            }
        ]

    resp = await client.messages.create(**body)
    usage = resp.usage
    return LLMCallResult(
        text=resp.content[0].text.strip(),
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        # SDK 老版本可能沒這些屬性 → getattr 保守防禦
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        model=model,
    )


def _join_blocks_by_role(
    blocks: list[PromptBlock],
) -> tuple[str, str]:
    """拼 blocks 成 (system_text, user_text)，分別按 role 排序。"""
    system_text = "\n\n".join(
        b.text for b in blocks if b.role == BlockRole.SYSTEM
    )
    user_text = "\n\n".join(
        b.text for b in blocks if b.role == BlockRole.USER
    )
    return system_text, user_text


def _parse_openai_cache_tokens(
    usage: dict[str, Any], provider: str
) -> tuple[int, int]:
    """解析 OpenAI-compatible response 的 cache token，跨 provider 形狀通吃。

    優先序（多形狀都試）：
    1. **Anthropic 形狀**（LiteLLM 代理 Claude / Bedrock 時 LiteLLM 直接 forward
       `cache_read_input_tokens` / `cache_creation_input_tokens` 到 usage 物件）
       — 命中 ≠ 0 才用，避免覆蓋掉其他形狀的有效值
    2. **DeepSeek 形狀**：`prompt_cache_hit_tokens`
    3. **OpenAI 形狀**：`prompt_tokens_details.cached_tokens`
    4. fallback 0

    Returns:
        (cache_read_tokens, cache_creation_tokens)
    """
    # 1. Anthropic 形狀（LiteLLM-Anthropic / Bedrock-Anthropic）
    anth_read = usage.get("cache_read_input_tokens", 0) or 0
    anth_create = usage.get("cache_creation_input_tokens", 0) or 0
    if anth_read or anth_create:
        return anth_read, anth_create

    # 2. DeepSeek 特有欄位
    if provider == "deepseek":
        hit = usage.get("prompt_cache_hit_tokens", 0) or 0
        # DeepSeek 的 miss 概念接近 creation，但計費模式不同，保守先歸 0
        return hit, 0

    # 3. OpenAI / Gemini / OpenRouter：prompt_tokens_details.cached_tokens
    details = usage.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens", 0) or 0
    return cached, 0


def _has_cache_hint(blocks: list[PromptBlock]) -> bool:
    """是否任一 block 標記 EPHEMERAL — 決定是否送結構化 content。"""
    return any(b.cache == CacheHint.EPHEMERAL for b in blocks)


def _to_openai_content_array(
    blocks: list[PromptBlock], role: BlockRole
) -> list[dict[str, Any]]:
    """把同 role 的 blocks 轉成 OpenAI 結構化 content array，**保留 cache_control**。

    LiteLLM 代理 Anthropic 模型時會把 cache_control 直接 pass-through 給 Anthropic
    API；OpenAI / Gemini 等不支援 cache_control 但接受結構化 content（marker 被忽略）。
    """
    items: list[dict[str, Any]] = []
    for b in blocks:
        if b.role != role:
            continue
        item: dict[str, Any] = {"type": "text", "text": b.text}
        if b.cache == CacheHint.EPHEMERAL:
            item["cache_control"] = {"type": "ephemeral"}
        items.append(item)
    return items


async def _call_openai_compatible(
    api_key: str,
    model: str,
    blocks: list[PromptBlock],
    max_tokens: int,
    base_url: str,
    provider: str,
) -> LLMCallResult:
    import httpx

    use_structured = _has_cache_hint(blocks)
    messages: list[dict[str, Any]] = []

    if use_structured:
        # S-LLM-Cache.1.1: 結構化 content 保留 cache_control marker
        # 主要為了 LiteLLM 代理 Anthropic 模型時能 pass-through cache 設定
        sys_items = _to_openai_content_array(blocks, BlockRole.SYSTEM)
        usr_items = _to_openai_content_array(blocks, BlockRole.USER)
        if sys_items:
            messages.append({"role": "system", "content": sys_items})
        if usr_items:
            messages.append({"role": "user", "content": usr_items})
    else:
        # 無 cache hint → 拼字串最精簡（OpenAI auto-prefix 對 byte-stable prefix
        # 一樣有效；不送 cache_control 不影響）
        system_text, user_text = _join_blocks_by_role(blocks)
        if system_text:
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": user_text})

    url = f"{base_url}/chat/completions"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage", {})
        cache_read, cache_creation = _parse_openai_cache_tokens(usage, provider)
        return LLMCallResult(
            text=text,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
            model=model,
        )
