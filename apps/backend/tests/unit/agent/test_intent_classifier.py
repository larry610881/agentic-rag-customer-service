"""Unit tests for IntentClassifier."""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock

from src.application.agent.intent_classifier import IntentClassifier
from src.domain.bot.entity import IntentRoute


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@dataclass
class FakeLLMResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


def _make_routes() -> list[IntentRoute]:
    return [
        IntentRoute(name="查詢", description="用戶詢問產品或服務相關問題", system_prompt="你是查詢助手"),
        IntentRoute(name="客訴", description="用戶表達不滿或投訴", system_prompt="你是客訴處理專員"),
        IntentRoute(name="閒聊", description="用戶進行閒聊或打招呼", system_prompt="你是閒聊夥伴"),
    ]


def _make_classifier():
    mock_llm = AsyncMock()
    classifier = IntentClassifier(llm_service=mock_llm)
    return classifier, mock_llm


def test_classify_exact_match():
    """When LLM returns exact route name, the corresponding route is returned."""
    classifier, mock_llm = _make_classifier()
    mock_llm.generate.return_value = FakeLLMResult(text="客訴")

    result = _run(classifier.classify("我要投訴！", "", _make_routes()))

    assert result is not None
    assert result.name == "客訴"
    assert result.system_prompt == "你是客訴處理專員"


def test_classify_with_whitespace():
    """LLM output with whitespace is still matched."""
    classifier, mock_llm = _make_classifier()
    mock_llm.generate.return_value = FakeLLMResult(text="  查詢  \n")

    result = _run(classifier.classify("請問有什麼商品？", "", _make_routes()))

    assert result is not None
    assert result.name == "查詢"


def test_classify_none_response():
    """When LLM returns NONE, classifier returns None (fallback)."""
    classifier, mock_llm = _make_classifier()
    mock_llm.generate.return_value = FakeLLMResult(text="NONE")

    result = _run(classifier.classify("隨便說說", "", _make_routes()))

    assert result is None


def test_classify_empty_routes():
    """Empty routes list returns None without calling LLM."""
    classifier, mock_llm = _make_classifier()

    result = _run(classifier.classify("hello", "", []))

    assert result is None
    mock_llm.generate.assert_not_called()


def test_classify_llm_error_returns_none():
    """LLM exception is caught, returns None (graceful fallback)."""
    classifier, mock_llm = _make_classifier()
    mock_llm.generate.side_effect = RuntimeError("LLM down")

    result = _run(classifier.classify("幫我查一下", "", _make_routes()))

    assert result is None


def test_classify_fuzzy_match():
    """When LLM returns text containing a route name, it is matched."""
    classifier, mock_llm = _make_classifier()
    mock_llm.generate.return_value = FakeLLMResult(text="我認為是查詢")

    result = _run(classifier.classify("請問價格？", "", _make_routes()))

    assert result is not None
    assert result.name == "查詢"


def test_classify_no_match():
    """When LLM returns unrecognized text, returns None."""
    classifier, mock_llm = _make_classifier()
    mock_llm.generate.return_value = FakeLLMResult(text="未知類別")

    result = _run(classifier.classify("xyz", "", _make_routes()))

    assert result is None


def test_classify_passes_correct_params():
    """Verify LLM is called with temperature=0, max_tokens=50."""
    classifier, mock_llm = _make_classifier()
    mock_llm.generate.return_value = FakeLLMResult(text="NONE")

    _run(classifier.classify("test", "一些歷史", _make_routes()))

    mock_llm.generate.assert_called_once()
    call_kwargs = mock_llm.generate.call_args
    assert call_kwargs.kwargs["temperature"] == 0
    assert call_kwargs.kwargs["max_tokens"] == 50
    # Verify router_context is included in the user_message prompt
    user_msg = call_kwargs.kwargs.get("user_message") or call_kwargs.args[1]
    assert "一些歷史" in user_msg
