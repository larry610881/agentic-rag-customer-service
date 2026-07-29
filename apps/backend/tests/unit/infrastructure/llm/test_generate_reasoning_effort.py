"""generate() reasoning_effort hint — Issue #52 E4 regression（第二輪）

2026-07-29 線上實證：temperature 剝除後 nano 分類呼叫 200，但
output_tokens=120（整個 max_completion_tokens 預算）且 content 為空 —
reasoning 模型把完成預算全燒在內部 reasoning，可見輸出 0 字 →
classifier 拿到空字串 → matched=None → 照樣 fallback。

契約：
1. LLMService.generate 接受 reasoning_effort hint（None = 不帶）
2. OpenAI impl：reasoning 模型（gpt-5/o-series）帶進 request body；
   非 reasoning 模型（gpt-4o）不帶（API 會拒絕）
3. Anthropic / Fake impl：接受參數但忽略（不噴 TypeError）
4. IntentClassifier 的分類呼叫帶 reasoning_effort='none'
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.infrastructure.llm.fake_llm_service import FakeLLMService
from src.infrastructure.llm.openai_llm_service import (
    OpenAILLMService,
    invalidate_unsupported_param_cache,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _reset_cache():
    invalidate_unsupported_param_cache()
    yield
    invalidate_unsupported_param_cache()


_OK_200 = {
    "choices": [{"message": {"content": "商品查詢\n包大人尿布"}}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 10},
}


def _make_service(model: str) -> tuple[OpenAILLMService, AsyncMock]:
    svc = OpenAILLMService(api_key="sk-test", model=model)
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=httpx.Response(
        status_code=200,
        json=_OK_200,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    ))
    svc._client = mock_client
    return svc, mock_client.post


def test_reasoning_model_sends_reasoning_effort():
    svc, post = _make_service("gpt-5-nano")
    _run(svc.generate(
        system_prompt="分類", user_message="q", context="",
        reasoning_effort="none",
    ))
    body = post.await_args.kwargs["json"]
    assert body["reasoning_effort"] == "none"


def test_non_reasoning_model_omits_reasoning_effort():
    svc, post = _make_service("gpt-4o-mini")
    _run(svc.generate(
        system_prompt="分類", user_message="q", context="",
        reasoning_effort="none",
    ))
    body = post.await_args.kwargs["json"]
    assert "reasoning_effort" not in body


def test_omitted_hint_not_sent():
    svc, post = _make_service("gpt-5-nano")
    _run(svc.generate(system_prompt="分類", user_message="q", context=""))
    body = post.await_args.kwargs["json"]
    assert "reasoning_effort" not in body


def test_fake_service_accepts_and_ignores():
    svc = FakeLLMService()
    result = _run(svc.generate(
        system_prompt="s", user_message="q", context="ctx",
        reasoning_effort="none",
    ))
    assert result.text


def test_intent_classifier_passes_effort_minimal():
    # 'minimal' 而非 'none'：線上實證 nano 拒收 'none'（unsupported_value
    # → 被剝除 → reasoning 照樣燒光預算）；'minimal' 為 gpt-5 家族通用值
    from src.application.agent.intent_classifier import IntentClassifier

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(
        return_value=MagicMock(text="商品查詢", usage=None)
    )
    classifier = IntentClassifier(llm_service=mock_llm)
    _run(classifier._call_llm(
        system_prompt="分類", user_message="有賣尿布嗎",
        route_names=["商品查詢"],
    ))
    kwargs = mock_llm.generate.await_args.kwargs
    assert kwargs["reasoning_effort"] == "minimal"


def _make_worker(name: str):
    from src.domain.bot.worker_config import WorkerConfig

    return WorkerConfig(bot_id="B001", name=name, description=name)


def test_classifier_empty_output_retries_with_default_model():
    """Issue #52 安全網：router 小模型輸出空 → 用預設模型重試一次。"""
    from src.application.agent.intent_classifier import IntentClassifier

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(side_effect=[
        MagicMock(text="", usage=None),        # nano 空輸出
        MagicMock(text="商品查詢\n尿布 特價", usage=None),  # 預設模型重試
    ])
    classifier = IntentClassifier(llm_service=mock_llm)
    worker = _make_worker("商品查詢")
    matched, rewritten = _run(classifier.classify_workers_and_rewrite(
        user_message="有賣尿布嗎",
        router_context="",
        workers=[worker],
        router_model="openai:gpt-5-nano",
    ))
    assert matched is worker
    assert rewritten == "尿布 特價"
    assert mock_llm.generate.await_count == 2
    first_kwargs = mock_llm.generate.await_args_list[0].kwargs
    second_kwargs = mock_llm.generate.await_args_list[1].kwargs
    assert first_kwargs.get("model") == "openai:gpt-5-nano"
    assert "model" not in second_kwargs  # 重試不帶 router 覆寫 → 預設模型


def test_classifier_no_retry_when_output_valid():
    from src.application.agent.intent_classifier import IntentClassifier

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(
        return_value=MagicMock(text="商品查詢", usage=None)
    )
    classifier = IntentClassifier(llm_service=mock_llm)
    worker = _make_worker("商品查詢")
    matched, _ = _run(classifier.classify_workers_and_rewrite(
        user_message="有賣尿布嗎",
        router_context="",
        workers=[worker],
        router_model="openai:gpt-5-nano",
    ))
    assert matched is worker
    assert mock_llm.generate.await_count == 1


def test_classifier_no_retry_without_router_model():
    """未設 router_model（已是預設模型）時空輸出不重試 — 避免無意義雙呼叫。"""
    from src.application.agent.intent_classifier import IntentClassifier

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=MagicMock(text="", usage=None))
    classifier = IntentClassifier(llm_service=mock_llm)
    matched, rewritten = _run(classifier.classify_workers_and_rewrite(
        user_message="有賣尿布嗎",
        router_context="",
        workers=[_make_worker("商品查詢")],
        router_model="",
    ))
    assert matched is None
    assert rewritten == ""
    assert mock_llm.generate.await_count == 1
