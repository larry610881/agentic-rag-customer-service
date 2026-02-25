"""Dynamic Embedding Factory BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.platform.entity import ProviderSetting
from src.domain.platform.value_objects import (
    ModelConfig,
    ProviderName,
    ProviderSettingId,
    ProviderType,
)
from src.infrastructure.embedding.dynamic_embedding_factory import (
    DynamicEmbeddingServiceFactory,
    DynamicEmbeddingServiceProxy,
)

scenarios("unit/platform/dynamic_embedding_factory.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def mock_encryption():
    svc = MagicMock()
    svc.decrypt = lambda text: text.replace("enc:", "")
    return svc


@pytest.fixture
def fallback_service():
    svc = AsyncMock()
    svc._is_fallback = True
    svc.embed_texts = AsyncMock(return_value=[[0.1] * 3])
    svc.embed_query = AsyncMock(return_value=[0.2] * 3)
    return svc


# --- DB 有啟用設定 ---


@given("DB 中有一個啟用的 Embedding 供應商設定")
def db_has_enabled_embedding(context, mock_repo, mock_encryption):
    setting = ProviderSetting(
        id=ProviderSettingId(value="e1"),
        provider_type=ProviderType.EMBEDDING,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI Embedding",
        is_enabled=True,
        api_key_encrypted="enc:sk-embed",
        base_url="https://api.openai.com/v1",
        models=[
            ModelConfig(
                model_id="text-embedding-3-small",
                display_name="Small",
                is_default=True,
            )
        ],
    )
    mock_repo.find_all_by_type = AsyncMock(return_value=[setting])
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption


@when("工廠解析 Embedding 服務")
def resolve_embedding_service(context, fallback_service):
    factory = DynamicEmbeddingServiceFactory(
        provider_setting_repository=context["repo"],
        encryption_service=context["encryption"],
        fallback_service=fallback_service,
    )
    context["result"] = _run(factory.get_service())
    context["fallback"] = fallback_service


@then("應回傳 DB 來源的 Embedding 服務")
def db_embedding_returned(context):
    assert context["result"] is not context["fallback"]


@then("應回傳 fallback 的 Embedding 服務")
def fallback_embedding_returned(context):
    assert context["result"] is context["fallback"]


# --- DB 無設定 ---


@given("DB 中沒有任何 Embedding 供應商設定")
def db_has_no_embedding(context, mock_repo, mock_encryption):
    mock_repo.find_all_by_type = AsyncMock(return_value=[])
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption


# --- DB 全停用 ---


@given("DB 中的 Embedding 供應商設定全部停用")
def db_embedding_all_disabled(context, mock_repo, mock_encryption):
    setting = ProviderSetting(
        id=ProviderSettingId(value="e1"),
        provider_type=ProviderType.EMBEDDING,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI",
        is_enabled=False,
        api_key_encrypted="enc:key",
    )
    mock_repo.find_all_by_type = AsyncMock(return_value=[setting])
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption


# --- Fake provider ---


@given("DB 中有一個啟用的 Fake Embedding 供應商設定")
def db_has_fake_embedding(context, mock_repo, mock_encryption):
    setting = ProviderSetting(
        id=ProviderSettingId(value="e2"),
        provider_type=ProviderType.EMBEDDING,
        provider_name=ProviderName.FAKE,
        display_name="Fake Embedding",
        is_enabled=True,
        api_key_encrypted="enc:fake-key",
    )
    mock_repo.find_all_by_type = AsyncMock(return_value=[setting])
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption


# --- Proxy embed_texts ---


@when("Proxy 呼叫 embed_texts")
def proxy_call_embed_texts(context, fallback_service):
    factory = DynamicEmbeddingServiceFactory(
        provider_setting_repository=context["repo"],
        encryption_service=context["encryption"],
        fallback_service=fallback_service,
    )
    proxy = DynamicEmbeddingServiceProxy(factory=factory)
    context["embed_result"] = _run(proxy.embed_texts(["hello"]))
    context["fallback"] = fallback_service


@then("應透過 fallback 服務執行 embed_texts")
def verify_embed_texts(context):
    context["fallback"].embed_texts.assert_called_once_with(["hello"])
    assert context["embed_result"] == [[0.1] * 3]


# --- Proxy embed_query ---


@when("Proxy 呼叫 embed_query")
def proxy_call_embed_query(context, fallback_service):
    factory = DynamicEmbeddingServiceFactory(
        provider_setting_repository=context["repo"],
        encryption_service=context["encryption"],
        fallback_service=fallback_service,
    )
    proxy = DynamicEmbeddingServiceProxy(factory=factory)
    context["query_result"] = _run(proxy.embed_query("hello"))
    context["fallback"] = fallback_service


@then("應透過 fallback 服務執行 embed_query")
def verify_embed_query(context):
    context["fallback"].embed_query.assert_called_once_with("hello")
    assert context["query_result"] == [0.2] * 3
