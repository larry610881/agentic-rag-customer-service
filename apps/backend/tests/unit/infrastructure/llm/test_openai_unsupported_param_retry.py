"""OpenAI 不支援參數自動剝除重試 — Issue #52 E4 regression

2026-07-29 線上實證：router_model 換 gpt-5-nano 後，意圖分類每次 400 —
"Unsupported value: 'temperature' does not support 0 with this model."
（param=temperature, code=unsupported_value）。classifier 固定帶
temperature=0，gpt-5.4 容忍但 nano（純 reasoning 模型）拒絕 → 分類
全滅靜默 fallback，快速道整條失效。

契約：
1. 400 unsupported_value/unsupported_parameter + 指名 param → 剝除該參數
   重試一次，成功回傳結果
2. 剝除結果記進 module-level cache → 同 model 後續呼叫直接預剝，不再 400
3. 其他 400（如 auth）維持原樣拋出，不重試
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

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


_ERROR_400 = {
    "error": {
        "message": (
            "Unsupported value: 'temperature' does not support 0 with "
            "this model. Only the default (1) value is supported."
        ),
        "type": "invalid_request_error",
        "param": "temperature",
        "code": "unsupported_value",
    }
}

_OK_200 = {
    "choices": [{"message": {"content": "商品查詢\n沙拉油 特價"}}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 10},
}


def _response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=payload,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )


def _make_service(post_side_effects: list) -> tuple[OpenAILLMService, AsyncMock]:
    svc = OpenAILLMService(api_key="sk-test", model="gpt-5-nano")
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=post_side_effects)
    svc._client = mock_client
    return svc, mock_client.post


def test_unsupported_param_stripped_and_retried():
    svc, post = _make_service([
        _response(400, _ERROR_400),
        _response(200, _OK_200),
    ])
    result = _run(svc.generate(
        system_prompt="分類",
        user_message="有賣沙拉油嗎",
        context="",
        temperature=0,
        max_tokens=120,
    ))
    assert "商品查詢" in result.text
    assert post.await_count == 2
    retry_body = post.await_args.kwargs["json"]
    assert "temperature" not in retry_body


def test_learned_param_pre_stripped_on_next_call():
    svc, post = _make_service([
        _response(400, _ERROR_400),
        _response(200, _OK_200),
        _response(200, _OK_200),
    ])
    _run(svc.generate(
        system_prompt="分類", user_message="q1", context="", temperature=0
    ))
    _run(svc.generate(
        system_prompt="分類", user_message="q2", context="", temperature=0
    ))
    # 第二次呼叫（第三個 request）應直接不帶 temperature，總共 3 個 request
    assert post.await_count == 3
    third_body = post.await_args.kwargs["json"]
    assert "temperature" not in third_body


def test_other_400_still_raises():
    auth_error = {
        "error": {
            "message": "Incorrect API key",
            "type": "invalid_request_error",
            "param": None,
            "code": "invalid_api_key",
        }
    }
    svc, post = _make_service([_response(400, auth_error)])
    with pytest.raises(httpx.HTTPStatusError):
        _run(svc.generate(
            system_prompt="分類", user_message="q", context="", temperature=0
        ))
    assert post.await_count == 1
