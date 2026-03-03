"""Dynamic Embedding Factory BDD Step Definitions

Embedding is fixed to OpenAI text-embedding-3-small.
API key resolution: DB (OpenAI LLM) → DB (OpenAI Embedding legacy) → .env.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.platform.entity import ProviderSetting
from src.domain.platform.value_objects import (
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


# --- DB 有 OpenAI LLM 設定含 API key ---


@given("DB 中有 OpenAI LLM 供應商設定含 API key")
def db_has_openai_llm(context, mock_repo, mock_encryption):
    setting = ProviderSetting(
        id=ProviderSettingId(value="s1"),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI LLM",
        is_enabled=True,
        api_key_encrypted="enc:sk-embed",
    )
    mock_repo.find_by_type_and_name = AsyncMock(return_value=setting)
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption


@when("工廠解析 Embedding 服務")
def resolve_embedding_service(context, fallback_service):
    factory = DynamicEmbeddingServiceFactory(
        provider_setting_repo_factory=lambda: context["repo"],
        encryption_service=context["encryption"],
        fallback_service=fallback_service,
    )
    context["result"] = _run(factory.get_service())
    context["fallback"] = fallback_service


@then("應回傳 OpenAI Embedding 服務")
def openai_embedding_returned(context):
    from src.infrastructure.embedding.openai_embedding_service import (
        OpenAIEmbeddingService,
    )
    assert isinstance(context["result"], OpenAIEmbeddingService)


@then("應回傳 fallback 的 Embedding 服務")
def fallback_embedding_returned(context):
    assert context["result"] is context["fallback"]


# --- DB 無設定且 .env 也無 key ---


@given("DB 中沒有任何供應商設定且 .env 無 OpenAI key")
def db_empty_env_empty(context, mock_repo, mock_encryption):
    mock_repo.find_by_type_and_name = AsyncMock(return_value=None)
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption
    # Patch Settings to return empty keys
    context["settings_patch"] = patch(
        "src.infrastructure.embedding.dynamic_embedding_factory.Settings",
        return_value=MagicMock(
            effective_embedding_api_key="",
            effective_openai_api_key="",
        ),
    )
    context["settings_patch"].start()


@pytest.fixture(autouse=True)
def cleanup_patches(context):
    yield
    if "settings_patch" in context:
        context["settings_patch"].stop()


# --- DB 有設定但無 API key ---


@given("DB 中有供應商設定但無 API key 且 .env 無 OpenAI key")
def db_has_setting_no_key(context, mock_repo, mock_encryption):
    setting = ProviderSetting(
        id=ProviderSettingId(value="s1"),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI",
        is_enabled=True,
        api_key_encrypted="",
    )
    mock_repo.find_by_type_and_name = AsyncMock(return_value=setting)
    context["repo"] = mock_repo
    context["encryption"] = mock_encryption
    context["settings_patch"] = patch(
        "src.infrastructure.embedding.dynamic_embedding_factory.Settings",
        return_value=MagicMock(
            effective_embedding_api_key="",
            effective_openai_api_key="",
        ),
    )
    context["settings_patch"].start()


# --- Proxy embed_texts ---


@when("Proxy 呼叫 embed_texts")
def proxy_call_embed_texts(context, fallback_service):
    factory = DynamicEmbeddingServiceFactory(
        provider_setting_repo_factory=lambda: context["repo"],
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
        provider_setting_repo_factory=lambda: context["repo"],
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
