"""Regression (S-KB-Followup.2): DynamicLLMServiceProxy.generate 支援 model kwarg.

Pre-fix bug：intent_classify / conversation_summary 呼叫 proxy.generate() 不傳
provider → factory fallback enabled[0]（大多情況 openai），結果 Carrefour bot
設定 litellm/haiku 但 intent_classify 紀錄用 gpt-5.2（系統 default）。
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.llm.dynamic_llm_factory import (
    DynamicLLMServiceProxy,
    _split_model_spec,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("", ("", "")),
        ("gpt-4o", ("", "gpt-4o")),
        ("litellm:azure_ai/claude-haiku-4-5",
         ("litellm", "azure_ai/claude-haiku-4-5")),
        ("anthropic:claude-sonnet-4", ("anthropic", "claude-sonnet-4")),
        # 有「:」在 model name 中（openrouter style "openai/gpt-4o"）
        # 只 split 一次
        ("openrouter:openai/gpt-4o-mini", ("openrouter", "openai/gpt-4o-mini")),
    ],
)
def test_split_model_spec(spec, expected):
    assert _split_model_spec(spec) == expected


def _build_mock_proxy():
    from src.domain.rag.value_objects import LLMResult, TokenUsage

    mock_service = AsyncMock()
    mock_service.generate = AsyncMock(
        return_value=LLMResult(
            text="ok",
            usage=TokenUsage(model="test", input_tokens=1, output_tokens=1),
        )
    )
    factory = MagicMock()
    factory.get_service = AsyncMock(return_value=mock_service)
    return DynamicLLMServiceProxy(factory=factory), factory


def test_proxy_generate_passes_provider_when_model_has_prefix():
    """proxy.generate(model='litellm:haiku') 必須傳 provider_name='litellm' 給 factory."""
    proxy, factory = _build_mock_proxy()
    result = _run(
        proxy.generate(
            system_prompt="s", user_message="u", context="",
            model="litellm:azure_ai/claude-haiku-4-5",
        )
    )
    factory.get_service.assert_awaited_once_with(
        provider_name="litellm",
        model="azure_ai/claude-haiku-4-5",
    )
    assert result.text == "ok"


def test_proxy_generate_no_prefix_bare_model():
    """proxy.generate(model='gpt-4o') 傳 provider_name='' 讓 factory 自行決定."""
    proxy, factory = _build_mock_proxy()
    _run(
        proxy.generate(
            system_prompt="s", user_message="u", context="", model="gpt-4o",
        )
    )
    factory.get_service.assert_awaited_once_with(
        provider_name="",
        model="gpt-4o",
    )


def test_proxy_generate_no_model_empty():
    """proxy.generate() 無 model → get_service('', '')."""
    proxy, factory = _build_mock_proxy()
    _run(
        proxy.generate(system_prompt="s", user_message="u", context="")
    )
    factory.get_service.assert_awaited_once_with(provider_name="", model="")
