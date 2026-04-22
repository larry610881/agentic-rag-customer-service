"""IntentClassifier prompt shape — S-LLM-Cache.1 Step 7。

驗證 categories 列表進 system_prompt（讓 AnthropicLLMService cache_control 涵蓋），
user_message 只含對話上下文與當下訊息。
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.agent.intent_classifier import IntentClassifier
from src.domain.bot.entity import IntentRoute


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def mock_llm_service():
    svc = AsyncMock()
    svc.generate = AsyncMock(
        return_value=SimpleNamespace(
            text="退貨",
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=2,
                total_tokens=12,
                model="anthropic:claude-haiku-4-5",
            ),
        )
    )
    return svc


def test_categories_appear_in_system_prompt_not_user_message(mock_llm_service):
    """類別列表必須出現在 system_prompt（cacheable），不在 user_message。"""
    classifier = IntentClassifier(llm_service=mock_llm_service, record_usage=None)
    routes = [
        IntentRoute(name="退貨", description="客戶詢問退貨流程", system_prompt=""),
        IntentRoute(name="出貨", description="客戶詢問出貨進度", system_prompt=""),
        IntentRoute(name="閒聊", description="一般對話", system_prompt=""),
    ]

    _run(
        classifier.classify(
            user_message="我想退貨",
            router_context="客戶剛剛表達不滿",
            intent_routes=routes,
            tenant_id="t-1",
        )
    )

    call_kwargs = mock_llm_service.generate.call_args.kwargs
    system_prompt = call_kwargs["system_prompt"]
    user_message = call_kwargs["user_message"]

    # 類別列表（含描述）必須在 system_prompt
    assert "類別" in system_prompt
    assert "退貨: 客戶詢問退貨流程" in system_prompt
    assert "出貨: 客戶詢問出貨進度" in system_prompt
    assert "閒聊: 一般對話" in system_prompt

    # 類別**不應**出現在 user_message
    assert "客戶詢問退貨流程" not in user_message
    assert "客戶詢問出貨進度" not in user_message

    # user_message 應只含對話上下文 + 當下訊息
    assert "客戶剛剛表達不滿" in user_message
    assert "我想退貨" in user_message


def test_router_context_optional_in_user_message(mock_llm_service):
    """無 router_context 時 user_message 只有用戶訊息。"""
    classifier = IntentClassifier(llm_service=mock_llm_service, record_usage=None)
    routes = [
        IntentRoute(name="閒聊", description="一般對話", system_prompt=""),
    ]

    _run(
        classifier.classify(
            user_message="哈囉",
            router_context="",
            intent_routes=routes,
            tenant_id="t-1",
        )
    )

    user_message = mock_llm_service.generate.call_args.kwargs["user_message"]
    assert "近期對話" not in user_message
    assert "哈囉" in user_message


def test_classify_workers_also_uses_system_categories(mock_llm_service):
    """classify_workers 路徑也要走相同 prompt shape（現代 sub-agent）。"""
    from src.domain.bot.worker_config import WorkerConfig

    classifier = IntentClassifier(llm_service=mock_llm_service, record_usage=None)
    workers = [
        WorkerConfig(
            id="w1",
            bot_id="b1",
            name="退貨專員",
            description="處理退貨相關詢問",
            worker_prompt="...",
        ),
    ]

    _run(
        classifier.classify_workers(
            user_message="退錢",
            router_context="",
            workers=workers,
            tenant_id="t-1",
        )
    )

    system_prompt = mock_llm_service.generate.call_args.kwargs["system_prompt"]
    assert "退貨專員: 處理退貨相關詢問" in system_prompt
