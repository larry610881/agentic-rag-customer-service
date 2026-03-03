"""Dynamic Factory Cache BDD Step Definitions"""

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
from src.infrastructure.cache.in_memory_cache_service import InMemoryCacheService
from src.infrastructure.embedding.dynamic_embedding_factory import (
    DynamicEmbeddingServiceFactory,
)
from src.infrastructure.llm.dynamic_llm_factory import DynamicLLMServiceFactory

scenarios("unit/platform/dynamic_factory_cache.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_encryption():
    """Create a mock encryption that does reversible transform."""
    svc = MagicMock()
    svc.encrypt = lambda text: f"ENC:{text}"
    svc.decrypt = lambda text: text.replace("ENC:", "", 1)
    return svc


@given("DB 中有啟用的 LLM 供應商設定且快取已啟用")
def llm_db_with_cache(context):
    mock_repo = AsyncMock()
    setting = ProviderSetting(
        id=ProviderSettingId(value="s1"),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI LLM",
        is_enabled=True,
        api_key_encrypted="sk-test",
        base_url="https://api.openai.com/v1",
        models=[
            ModelConfig(
                model_id="gpt-4o", display_name="GPT-4o", is_default=True
            )
        ],
    )
    mock_repo.find_all_by_type = AsyncMock(return_value=[setting])

    encryption = _make_encryption()
    cache_service = InMemoryCacheService()
    fallback = AsyncMock()

    context["factory"] = DynamicLLMServiceFactory(
        provider_setting_repo_factory=lambda: mock_repo,
        encryption_service=encryption,
        fallback_service=fallback,
        cache_service=cache_service,
        cache_ttl=300,
    )
    context["mock_repo"] = mock_repo
    context["factory_type"] = "llm"


@given("DB 中有啟用的 Embedding 供應商設定且快取已啟用")
def embedding_db_with_cache(context):
    mock_repo = AsyncMock()
    # Embedding factory now resolves API key from OpenAI LLM provider
    setting = ProviderSetting(
        id=ProviderSettingId(value="s2"),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName.OPENAI,
        display_name="OpenAI LLM",
        is_enabled=True,
        api_key_encrypted="sk-embed-test",
    )
    mock_repo.find_by_type_and_name = AsyncMock(return_value=setting)

    encryption = _make_encryption()
    cache_service = InMemoryCacheService()
    fallback = AsyncMock()

    context["factory"] = DynamicEmbeddingServiceFactory(
        provider_setting_repo_factory=lambda: mock_repo,
        encryption_service=encryption,
        fallback_service=fallback,
        cache_service=cache_service,
        cache_ttl=300,
    )
    context["mock_repo"] = mock_repo
    context["factory_type"] = "embedding"


@when("連續兩次解析 LLM 服務")
def resolve_llm_twice(context):
    for _ in range(2):
        _run(context["factory"].get_service())


@when("連續兩次解析 Embedding 服務")
def resolve_embedding_twice(context):
    for _ in range(2):
        _run(context["factory"].get_service())


@then("DB 查詢應只執行一次")
def verify_single_db_call(context):
    if context["factory_type"] == "llm":
        assert context["mock_repo"].find_all_by_type.call_count == 1
    else:
        # Embedding factory uses find_by_type_and_name (called once, cached)
        assert context["mock_repo"].find_by_type_and_name.call_count == 1
