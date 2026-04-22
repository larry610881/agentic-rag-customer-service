"""_call_openai_compatible unit tests — S-LLM-Cache.1 Step 4.

涵蓋 openai / deepseek / qwen / ollama 等 OpenAI-compatible providers。
驗證 blocks 按 role 拼字串、cache_control 忽略、cache_tokens 解析。
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from src.domain.llm import BlockRole, CacheHint, PromptBlock
from src.infrastructure.llm.llm_caller import call_llm


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_httpx_response(
    text: str = "ok",
    prompt_tokens: int = 100,
    completion_tokens: int = 20,
    cached_tokens: int = 0,
    deepseek_hit_tokens: int | None = None,
):
    """Build mock httpx Response.json() data matching OpenAI shape."""
    usage: dict = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    if cached_tokens > 0:
        usage["prompt_tokens_details"] = {"cached_tokens": cached_tokens}
    if deepseek_hit_tokens is not None:
        usage["prompt_cache_hit_tokens"] = deepseek_hit_tokens

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: {
        "choices": [{"message": {"content": text}}],
        "usage": usage,
    }
    return mock_resp


async def _fake_key_resolver(provider: str) -> str:
    return "fake-api-key"


def _patch_httpx(mock_response):
    """Helper context for httpx.AsyncClient.post mock."""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)
    return patch("httpx.AsyncClient", return_value=mock_client), mock_client


def test_openai_flat_string_backwards_compatible():
    """flat string prompt → 包成單一 user message。"""
    mock_resp = _mock_httpx_response(text="hi", prompt_tokens=42)
    cm, mock_client = _patch_httpx(mock_resp)
    with cm:
        result = _run(
            call_llm(
                model_spec="openai:gpt-4o-mini",
                prompt="hello world",
                max_tokens=50,
                api_key_resolver=_fake_key_resolver,
            )
        )

    assert result.text == "hi"
    assert result.input_tokens == 42
    assert result.cache_read_tokens == 0

    body = mock_client.post.call_args.kwargs["json"]
    assert body["messages"] == [{"role": "user", "content": "hello world"}]


def test_openai_blocks_split_by_role_to_system_and_user_messages_no_cache_hint():
    """system + user blocks 都無 cache hint → 拼字串（精簡形式）。"""
    mock_resp = _mock_httpx_response()
    cm, mock_client = _patch_httpx(mock_resp)
    with cm:
        blocks = [
            PromptBlock(text="You are helpful.", role=BlockRole.SYSTEM, cache=CacheHint.NONE),
            PromptBlock(text="Big stable context...", role=BlockRole.USER, cache=CacheHint.NONE),
            PromptBlock(text="Question now.", role=BlockRole.USER, cache=CacheHint.NONE),
        ]
        _run(
            call_llm(
                model_spec="openai:gpt-4o-mini",
                prompt=blocks,
                max_tokens=50,
                api_key_resolver=_fake_key_resolver,
            )
        )

    body = mock_client.post.call_args.kwargs["json"]
    assert body["messages"] == [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Big stable context...\n\nQuestion now."},
    ]


def test_openai_blocks_with_cache_hint_send_structured_content():
    """S-LLM-Cache.1.1: cacheable blocks → 結構化 content array (含 cache_control)。
    OpenAI 直連雖會忽略 cache_control 但接受結構化 content；prefix stable 仍能命中
    auto-prefix cache。"""
    mock_resp = _mock_httpx_response()
    cm, mock_client = _patch_httpx(mock_resp)
    with cm:
        blocks = [
            PromptBlock(text="You are helpful.", role=BlockRole.SYSTEM, cache=CacheHint.EPHEMERAL),
            PromptBlock(text="Question now.", role=BlockRole.USER, cache=CacheHint.NONE),
        ]
        _run(
            call_llm(
                model_spec="openai:gpt-4o-mini",
                prompt=blocks,
                max_tokens=50,
                api_key_resolver=_fake_key_resolver,
            )
        )

    body = mock_client.post.call_args.kwargs["json"]
    assert body["messages"] == [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are helpful.",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        },
        {
            "role": "user",
            "content": [{"type": "text", "text": "Question now."}],
        },
    ]


def test_openai_parses_cached_tokens_from_prompt_tokens_details():
    """OpenAI usage.prompt_tokens_details.cached_tokens → cache_read_tokens。"""
    mock_resp = _mock_httpx_response(
        prompt_tokens=1500,
        completion_tokens=30,
        cached_tokens=1200,
    )
    cm, _ = _patch_httpx(mock_resp)
    with cm:
        result = _run(
            call_llm(
                model_spec="openai:gpt-4o-mini",
                prompt="x",
                max_tokens=50,
                api_key_resolver=_fake_key_resolver,
            )
        )

    assert result.input_tokens == 1500
    assert result.cache_read_tokens == 1200
    assert result.cache_creation_tokens == 0  # OpenAI 無 creation 概念


def test_deepseek_parses_prompt_cache_hit_tokens_special_field():
    """DeepSeek 用非標準欄位 prompt_cache_hit_tokens。"""
    mock_resp = _mock_httpx_response(
        prompt_tokens=2000,
        completion_tokens=20,
        deepseek_hit_tokens=1800,
    )
    cm, _ = _patch_httpx(mock_resp)
    with cm:
        result = _run(
            call_llm(
                model_spec="deepseek:deepseek-chat",
                prompt="x",
                max_tokens=50,
                api_key_resolver=_fake_key_resolver,
            )
        )

    assert result.input_tokens == 2000
    assert result.cache_read_tokens == 1800


def test_local_ollama_zero_cache_tokens_no_error():
    """本地 Ollama 通常無 usage.prompt_tokens_details → cache_tokens=0 不報錯。"""
    mock_resp = _mock_httpx_response(prompt_tokens=80, completion_tokens=15)
    cm, _ = _patch_httpx(mock_resp)
    with cm:
        result = _run(
            call_llm(
                model_spec="litellm:llama3:8b",
                prompt="ping",
                max_tokens=10,
                api_key_resolver=_fake_key_resolver,
            )
        )

    assert result.cache_read_tokens == 0
    assert result.cache_creation_tokens == 0
    assert result.input_tokens == 80


# === S-LLM-Cache.1.1: LiteLLM-Anthropic cache pass-through ===


def _mock_litellm_anthropic_response(
    prompt_tokens: int = 1500,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
):
    """LiteLLM 代理 Anthropic 時，usage 會帶 Anthropic 原生欄位。"""
    usage: dict = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": 30,
        "cache_read_input_tokens": cache_read_input_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
    }
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: {
        "choices": [{"message": {"content": "ok"}}],
        "usage": usage,
    }
    return mock_resp


def test_litellm_with_cache_hint_sends_structured_content_with_cache_control():
    """blocks 含 EPHEMERAL → messages content 必須是 array 並含 cache_control marker。
    這是 LiteLLM 代理 Claude 模型時讓 cache 命中的關鍵。"""
    mock_resp = _mock_litellm_anthropic_response()
    cm, mock_client = _patch_httpx(mock_resp)
    with cm:
        blocks = [
            PromptBlock(
                text="這是大段固定的 system 指令",
                role=BlockRole.SYSTEM,
                cache=CacheHint.EPHEMERAL,
            ),
            PromptBlock(
                text="使用者當下訊息",
                role=BlockRole.USER,
                cache=CacheHint.NONE,
            ),
        ]
        _run(
            call_llm(
                model_spec="litellm:azure_ai/claude-haiku-4-5",
                prompt=blocks,
                max_tokens=50,
                api_key_resolver=_fake_key_resolver,
            )
        )

    body = mock_client.post.call_args.kwargs["json"]
    assert body["messages"] == [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "這是大段固定的 system 指令",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        },
        {
            "role": "user",
            "content": [{"type": "text", "text": "使用者當下訊息"}],
        },
    ]


def test_litellm_anthropic_parses_cache_tokens_from_native_fields():
    """LiteLLM forward Claude usage 時帶 Anthropic 原生欄位
    (cache_read_input_tokens / cache_creation_input_tokens)。"""
    mock_resp = _mock_litellm_anthropic_response(
        prompt_tokens=2000,
        cache_read_input_tokens=1800,
        cache_creation_input_tokens=200,
    )
    cm, _ = _patch_httpx(mock_resp)
    with cm:
        result = _run(
            call_llm(
                model_spec="litellm:azure_ai/claude-haiku-4-5",
                prompt="x",
                max_tokens=50,
                api_key_resolver=_fake_key_resolver,
            )
        )

    assert result.cache_read_tokens == 1800
    assert result.cache_creation_tokens == 200


def test_litellm_no_cache_hint_still_uses_flat_string_for_efficiency():
    """無 cacheable block 時保留 flat string（避免無謂的 array overhead）。"""
    mock_resp = _mock_litellm_anthropic_response()
    cm, mock_client = _patch_httpx(mock_resp)
    with cm:
        blocks = [
            PromptBlock(text="instr", role=BlockRole.SYSTEM, cache=CacheHint.NONE),
            PromptBlock(text="msg", role=BlockRole.USER, cache=CacheHint.NONE),
        ]
        _run(
            call_llm(
                model_spec="litellm:azure_ai/claude-haiku-4-5",
                prompt=blocks,
                max_tokens=10,
                api_key_resolver=_fake_key_resolver,
            )
        )

    body = mock_client.post.call_args.kwargs["json"]
    assert body["messages"] == [
        {"role": "system", "content": "instr"},
        {"role": "user", "content": "msg"},
    ]
