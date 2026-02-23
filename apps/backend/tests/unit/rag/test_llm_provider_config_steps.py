"""LLM Provider Config BDD Step Definitions"""

import pytest
from pytest_bdd import given, parsers, scenarios, then

from src.config import Settings
from src.infrastructure.llm.openai_llm_service import OpenAILLMService

scenarios("unit/rag/llm_provider_config.feature")

DASHSCOPE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
OPENAI_URL = "https://api.openai.com/v1"


@pytest.fixture
def context():
    return {}


@given(
    parsers.parse(
        '建立 OpenAILLMService 時指定 base_url 為 "{base_url}"'
    ),
)
def create_service_with_base_url(context, base_url):
    context["service"] = OpenAILLMService(
        api_key="test-key",
        base_url=base_url,
    )


@given("建立 OpenAILLMService 時未指定 base_url")
def create_service_default(context):
    context["service"] = OpenAILLMService(api_key="test-key")


@given(
    parsers.parse(
        'Settings 設定 openai_api_key 為 "{new_key}" 且 openai_chat_api_key 為 "{old_key}"'
    ),
)
def create_settings(context, new_key, old_key):
    context["settings"] = Settings(
        openai_api_key=new_key,
        openai_chat_api_key=old_key,
    )


@then(
    parsers.parse('服務的 base_url 應為 "{expected_url}"'),
)
def verify_base_url(context, expected_url):
    assert context["service"]._base_url == expected_url


@given(
    parsers.parse(
        'Settings 未設定 openai_api_key 且 openai_chat_api_key 為 "{old_key}"'
    ),
)
def create_settings_fallback(context, old_key):
    context["settings"] = Settings(
        openai_api_key="",
        openai_chat_api_key=old_key,
    )


@then(
    parsers.parse('effective_openai_api_key 應為 "{expected_key}"'),
)
def verify_effective_key(context, expected_key):
    assert context["settings"].effective_openai_api_key == expected_key
