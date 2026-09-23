"""Regression：llm_rerank 對真實 anthropic SDK 的呼叫簽名（Issue #100 B4）。

anthropic SDK 1.x 的 ``AsyncMessages.create`` 已無 ``temperature`` 具名參數，
原本 ``create(..., temperature=0)`` 會在送出前就拋 TypeError，被
``except Exception`` 吞掉 → 每次都靜默退回原始順序（重排完全失效）。
既有測試以 MagicMock 取代 client，看不到這個問題；此處用真 SDK +
httpx MockTransport 攔截 HTTP 請求。
"""

import asyncio
import json
from typing import Any
from unittest.mock import patch

import anthropic
import httpx2 as httpx

from src.infrastructure.rag.llm_reranker import llm_rerank


def _make_client_factory(captured: list[dict[str, Any]]):
    real_cls = anthropic.AsyncAnthropic

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-haiku-4-5-20251001",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            [
                                {"index": 0, "score": 1},
                                {"index": 1, "score": 3},
                                {"index": 2, "score": 9},
                            ]
                        ),
                    }
                ],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    def factory(**kwargs: Any) -> anthropic.AsyncAnthropic:
        return real_cls(
            **kwargs,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            max_retries=0,
        )

    return factory


def _chunks() -> list[dict]:
    return [{"content": f"chunk-{i}"} for i in range(3)]


def _run_rerank(model: str) -> tuple[list[dict], list[dict[str, Any]]]:
    captured: list[dict[str, Any]] = []
    with patch("anthropic.AsyncAnthropic", _make_client_factory(captured)):
        result = asyncio.run(
            llm_rerank(
                "q", _chunks(), model=model, top_k=2, api_key="sk-test"
            )
        )
    return result, captured


def test_rerank_reorders_with_real_sdk_and_sends_temperature_zero() -> None:
    result, captured = _run_rerank("claude-haiku-4-5-20251001")

    assert len(captured) == 1, "SDK 應實際送出一次 HTTP 請求"
    assert [c["content"] for c in result] == ["chunk-2", "chunk-1"]
    assert captured[0]["temperature"] == 0


def test_rerank_omits_temperature_for_models_rejecting_sampling_params() -> None:
    result, captured = _run_rerank("claude-opus-5")

    assert len(captured) == 1
    assert [c["content"] for c in result] == ["chunk-2", "chunk-1"]
    assert "temperature" not in captured[0]
