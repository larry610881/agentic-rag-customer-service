"""Regression: OpenAIEmbeddingService fail-fast on empty / auth errors.

Bug 5/6 (carrefour DM reprocess): worker 在 Milvus 短暫斷線後 re-resolve
API key 拿到空字串，httpx 送出 `Bearer ` 觸發 LocalProtocolError，retry 5 次
浪費時間。改成空 key 直接 raise ValueError + 401/403 不 retry。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.infrastructure.embedding.openai_embedding_service import (
    OpenAIEmbeddingService,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_empty_api_key_raises_value_error_immediately():
    """空 api_key 不該送 HTTP request，直接 raise ValueError。"""
    svc = OpenAIEmbeddingService(api_key="", max_retries=5)
    # 應立即 raise，且不會嘗試 5 次（避免拖慢 fail）
    with pytest.raises(ValueError, match="API key is empty"):
        _run(svc.embed_texts(["hello"]))


def test_empty_api_key_message_includes_diagnostic():
    """error message 應含 model / base_url / 排查建議 — 給 user 自助 debug。"""
    svc = OpenAIEmbeddingService(
        api_key="",
        model="text-embedding-3-large",
        base_url="https://api.openai.com/v1",
    )
    try:
        _run(svc.embed_texts(["hello"]))
    except ValueError as e:
        assert "text-embedding-3-large" in str(e)
        assert "ProviderSetting" in str(e) or "provider key" in str(e)


def test_401_does_not_retry():
    """401 = invalid key，不 retry 5 次浪費 quota。"""
    svc = OpenAIEmbeddingService(api_key="sk-fake", max_retries=5)
    fake_response = MagicMock(spec=httpx.Response)
    fake_response.status_code = 401
    fake_response.text = "Invalid API key"
    fake_response.json = MagicMock(return_value={"error": {"message": "Invalid"}})
    fake_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401", request=MagicMock(), response=fake_response
        )
    )
    svc._client.post = AsyncMock(return_value=fake_response)

    with pytest.raises(httpx.HTTPStatusError):
        _run(svc.embed_texts(["hello"]))

    # 應只呼叫一次（沒 retry）
    assert svc._client.post.call_count == 1


def test_403_does_not_retry():
    """403 = forbidden（quota 用完 / org 不允許），同 401 不 retry。"""
    svc = OpenAIEmbeddingService(api_key="sk-fake", max_retries=5)
    fake_response = MagicMock(spec=httpx.Response)
    fake_response.status_code = 403
    fake_response.text = "Forbidden"
    fake_response.json = MagicMock(return_value={"error": {"message": "Forbidden"}})
    fake_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "403", request=MagicMock(), response=fake_response
        )
    )
    svc._client.post = AsyncMock(return_value=fake_response)

    with pytest.raises(httpx.HTTPStatusError):
        _run(svc.embed_texts(["hello"]))

    assert svc._client.post.call_count == 1


def test_500_does_retry():
    """500 = server error，仍走原 retry 邏輯（transient）。"""
    svc = OpenAIEmbeddingService(api_key="sk-fake", max_retries=2)
    fake_response = MagicMock(spec=httpx.Response)
    fake_response.status_code = 500
    fake_response.text = "Internal"
    fake_response.headers = {}
    fake_response.json = MagicMock(return_value={})
    fake_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "500", request=MagicMock(), response=fake_response
        )
    )
    svc._client.post = AsyncMock(return_value=fake_response)

    with pytest.raises(httpx.HTTPStatusError):
        _run(svc.embed_texts(["hello"]))

    # max_retries=2 → 2 次嘗試
    assert svc._client.post.call_count == 2
