"""_call_anthropic unit tests — S-LLM-Cache.1 Step 3.

驗證 block-based prompt 正確翻譯成 Anthropic API 格式、cache token 正確解析。
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.domain.llm import BlockRole, CacheHint, PromptBlock
from src.infrastructure.llm.llm_caller import LLMCallResult, call_llm


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_anthropic_response(
    text: str = "reply",
    input_tokens: int = 100,
    output_tokens: int = 20,
    cache_read: int = 0,
    cache_creation: int = 0,
):
    """Build a mock anthropic response object matching SDK shape."""
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_creation,
        ),
    )


async def _fake_key_resolver(provider: str) -> str:
    return "fake-api-key"


def test_flat_string_backwards_compatible():
    """舊 caller 傳 str prompt → 正常運作。"""
    with patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(text="ok", input_tokens=50)
        )
        mock_client_cls.return_value = mock_client

        result = _run(
            call_llm(
                model_spec="anthropic:claude-haiku-4-5",
                prompt="plain string prompt",
                max_tokens=100,
                api_key_resolver=_fake_key_resolver,
            )
        )

        assert isinstance(result, LLMCallResult)
        assert result.text == "ok"
        assert result.input_tokens == 50
        assert result.cache_read_tokens == 0
        assert result.cache_creation_tokens == 0

        # 驗證送出的 body 是單純 messages=[{role:user, content:str}]
        call_args = mock_client.messages.create.call_args.kwargs
        assert call_args["messages"] == [
            {"role": "user", "content": "plain string prompt"}
        ]
        # 單一無 cache block 不應出現 system 欄位
        assert "system" not in call_args


def test_cacheable_user_block_translates_to_content_array_with_marker():
    """cacheable user block 要加 cache_control 標記，content 用 array 形式。"""
    with patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response()
        )
        mock_client_cls.return_value = mock_client

        blocks = [
            PromptBlock(
                text="<document>big content</document>",
                role=BlockRole.USER,
                cache=CacheHint.EPHEMERAL,
            ),
            PromptBlock(
                text="what is this about?",
                role=BlockRole.USER,
                cache=CacheHint.NONE,
            ),
        ]
        _run(
            call_llm(
                model_spec="anthropic:claude-haiku-4-5",
                prompt=blocks,
                max_tokens=100,
                api_key_resolver=_fake_key_resolver,
            )
        )

        call_args = mock_client.messages.create.call_args.kwargs
        content = call_args["messages"][0]["content"]
        assert content == [
            {
                "type": "text",
                "text": "<document>big content</document>",
                "cache_control": {"type": "ephemeral"},
            },
            {"type": "text", "text": "what is this about?"},
        ]


def test_system_block_with_cache_marker_goes_to_system_array():
    """role=SYSTEM + cache=EPHEMERAL → Anthropic body.system 陣列。"""
    with patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response()
        )
        mock_client_cls.return_value = mock_client

        blocks = [
            PromptBlock(
                text="You are a safety reviewer.",
                role=BlockRole.SYSTEM,
                cache=CacheHint.EPHEMERAL,
            ),
            PromptBlock(
                text="Check this response: xxx",
                role=BlockRole.USER,
                cache=CacheHint.NONE,
            ),
        ]
        _run(
            call_llm(
                model_spec="anthropic:claude-haiku-4-5",
                prompt=blocks,
                max_tokens=100,
                api_key_resolver=_fake_key_resolver,
            )
        )

        call_args = mock_client.messages.create.call_args.kwargs
        assert call_args["system"] == [
            {
                "type": "text",
                "text": "You are a safety reviewer.",
                "cache_control": {"type": "ephemeral"},
            }
        ]
        # 單一無 cache user block → 用 string content 精簡
        assert call_args["messages"] == [
            {"role": "user", "content": "Check this response: xxx"}
        ]


def test_parses_cache_tokens_from_response():
    """Anthropic usage 的 cache_read/creation_input_tokens 要正確流到 LLMCallResult。"""
    with patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response(
                input_tokens=1200,
                output_tokens=30,
                cache_read=1000,     # 命中 cache
                cache_creation=0,
            )
        )
        mock_client_cls.return_value = mock_client

        result = _run(
            call_llm(
                model_spec="anthropic:claude-haiku-4-5",
                prompt="test",
                max_tokens=100,
                api_key_resolver=_fake_key_resolver,
            )
        )
        assert result.input_tokens == 1200
        assert result.cache_read_tokens == 1000
        assert result.cache_creation_tokens == 0


def test_handles_sdk_missing_cache_attributes_defensively():
    """老版 SDK response 沒 cache_read_input_tokens 屬性 → getattr fallback 0。"""
    with patch("anthropic.AsyncAnthropic") as mock_client_cls:
        mock_client = AsyncMock()
        # 沒有 cache_read_input_tokens / cache_creation_input_tokens 屬性
        mock_client.messages.create = AsyncMock(
            return_value=SimpleNamespace(
                content=[SimpleNamespace(text="ok")],
                usage=SimpleNamespace(input_tokens=50, output_tokens=10),
            )
        )
        mock_client_cls.return_value = mock_client

        result = _run(
            call_llm(
                model_spec="anthropic:claude-haiku-4-5",
                prompt="test",
                max_tokens=100,
                api_key_resolver=_fake_key_resolver,
            )
        )
        assert result.cache_read_tokens == 0
        assert result.cache_creation_tokens == 0
        assert result.input_tokens == 50
