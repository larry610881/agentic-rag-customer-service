"""Regression：E2E_MODE 必須同時擋掉真的 embedding 呼叫（Issue #65）。

E2E_MODE 的約定是「不打真的 LLM / embedding API」，但 container 只在 agent 上套用；
embedding 後備服務仍依 EMBEDDING_PROVIDER（預設 openai）建真的 OpenAI client。
整合測試因此在對話摘要語意搜尋、unified search 真的打到 api.openai.com（401）。
"""

from dependency_injector import providers

from src.config import Settings
from src.container import Container
from src.infrastructure.embedding.fake_embedding_service import FakeEmbeddingService
from src.infrastructure.embedding.openai_embedding_service import OpenAIEmbeddingService


def _static_embedding(**settings) -> object:
    container = Container()
    container.config.override(providers.Object(Settings(**settings)))
    try:
        return container._static_embedding_service()
    finally:
        container.config.reset_override()


def test_E2E_MODE_下即使設定_openai_也用假_embedding():
    svc = _static_embedding(e2e_mode=True, embedding_provider="openai")
    assert isinstance(svc, FakeEmbeddingService)


def test_非_E2E_MODE_照設定使用真的_embedding():
    svc = _static_embedding(e2e_mode=False, embedding_provider="openai")
    assert isinstance(svc, OpenAIEmbeddingService)


def test_E2E_MODE_下動態工廠不以環境變數的_key_建真的_embedding(monkeypatch):
    """工廠原本只在「沒有 key」時才退回後備；整合測試設了 sk-test-fake → 真的外連。"""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from src.infrastructure.embedding.dynamic_embedding_factory import (
        DynamicEmbeddingServiceFactory,
    )

    monkeypatch.setenv("E2E_MODE", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    fallback = FakeEmbeddingService(vector_size=8)
    repo_factory = MagicMock(return_value=AsyncMock())
    factory = DynamicEmbeddingServiceFactory(
        provider_setting_repo_factory=repo_factory,
        encryption_service=MagicMock(),
        fallback_service=fallback,
    )
    assert asyncio.run(factory.get_service()) is fallback
    repo_factory.assert_not_called()
