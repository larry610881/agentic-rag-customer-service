"""Layer 3 — provider API key TTLCache + invalidation."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.platform.entity import ProviderSetting
from src.domain.platform.value_objects import (
    ModelConfig,
    ProviderName,
    ProviderSettingId,
    ProviderType,
)
from src.infrastructure.llm.dynamic_llm_factory import (
    DynamicLLMServiceFactory,
    invalidate_provider_key_cache,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """每個 test 起始 cache 必須空。"""
    invalidate_provider_key_cache()
    yield
    invalidate_provider_key_cache()


def _make_setting(provider_name: str, encrypted_key: str) -> ProviderSetting:
    return ProviderSetting(
        id=ProviderSettingId(),
        provider_type=ProviderType.LLM,
        provider_name=ProviderName(provider_name),
        display_name="X",
        is_enabled=True,
        api_key_encrypted=encrypted_key,
        base_url="",
        models=[
            ModelConfig(
                model_id="m1",
                display_name="m1",
                is_default=True,
                is_enabled=True,
            ),
        ],
        extra_config={},
    )


def _make_factory(
    *,
    settings: list[ProviderSetting],
    decrypt_returns: dict[str, str] | None = None,
) -> tuple[DynamicLLMServiceFactory, MagicMock, MagicMock]:
    """Build factory with mocked repo + encryption."""
    repo = AsyncMock()
    repo.find_all_by_type = AsyncMock(return_value=settings)
    repo_factory = MagicMock(return_value=repo)

    encryption = MagicMock()
    decrypt_map = decrypt_returns or {}

    def _decrypt(token: str) -> str:
        return decrypt_map.get(token, token)

    encryption.decrypt = MagicMock(side_effect=_decrypt)

    factory = DynamicLLMServiceFactory(
        provider_setting_repo_factory=repo_factory,
        encryption_service=encryption,
        fallback_service=MagicMock(),
        cache_service=None,
    )
    return factory, repo, repo_factory


# ── DB hit, cache write ───────────────────────────────────────


def test_first_resolve_hits_db_and_writes_cache():
    setting = _make_setting("openai", "encrypted-token")
    factory, repo, repo_factory = _make_factory(
        settings=[setting],
        decrypt_returns={"encrypted-token": "sk-real-key"},
    )

    key = _run(factory.resolve_api_key("openai"))

    assert key == "sk-real-key"
    repo_factory.assert_called_once()


def test_second_resolve_uses_cache_no_db_call():
    setting = _make_setting("openai", "encrypted-token")
    factory, repo, repo_factory = _make_factory(
        settings=[setting],
        decrypt_returns={"encrypted-token": "sk-real-key"},
    )

    _run(factory.resolve_api_key("openai"))
    _run(factory.resolve_api_key("openai"))  # second hit

    assert repo_factory.call_count == 1, "second call should hit cache, not DB"


def test_invalidate_specific_provider_clears_only_that_key():
    setting1 = _make_setting("openai", "tk1")
    setting2 = _make_setting("anthropic", "tk2")
    factory, _, repo_factory = _make_factory(
        settings=[setting1, setting2],
        decrypt_returns={"tk1": "key-openai", "tk2": "key-anthropic"},
    )

    _run(factory.resolve_api_key("openai"))
    _run(factory.resolve_api_key("anthropic"))
    assert repo_factory.call_count == 2

    invalidate_provider_key_cache("openai")

    _run(factory.resolve_api_key("openai"))      # cache miss → DB
    _run(factory.resolve_api_key("anthropic"))   # cache hit → no DB

    assert repo_factory.call_count == 3, (
        "openai re-fetched after invalidate, anthropic still cached"
    )


def test_invalidate_all_clears_everything():
    setting = _make_setting("openai", "tk1")
    factory, _, repo_factory = _make_factory(
        settings=[setting],
        decrypt_returns={"tk1": "key-openai"},
    )

    _run(factory.resolve_api_key("openai"))
    invalidate_provider_key_cache()  # nuke all
    _run(factory.resolve_api_key("openai"))

    assert repo_factory.call_count == 2


# ── empty / fallback paths ──────────────────────────────────


def test_db_empty_falls_back_to_env_and_does_not_cache_empty(
    monkeypatch: pytest.MonkeyPatch,
):
    """DB 沒設 + env 沒設 → 回 ""，但 cache 不存空值（避免下次重試也拿空）。"""
    factory, _, repo_factory = _make_factory(settings=[])

    monkeypatch.setattr(
        "src.infrastructure.llm.dynamic_llm_factory.Settings",
        lambda: MagicMock(effective_openai_api_key=""),
    )

    key1 = _run(factory.resolve_api_key("openai"))
    key2 = _run(factory.resolve_api_key("openai"))

    assert key1 == ""
    assert key2 == ""
    # 兩次都打 DB（因為空值不 cache）
    assert repo_factory.call_count == 2


def test_db_fail_falls_back_to_env_and_caches_env_value(
    monkeypatch: pytest.MonkeyPatch,
):
    repo = AsyncMock()
    repo.find_all_by_type = AsyncMock(side_effect=Exception("db boom"))
    repo_factory = MagicMock(return_value=repo)

    factory = DynamicLLMServiceFactory(
        provider_setting_repo_factory=repo_factory,
        encryption_service=MagicMock(),
        fallback_service=MagicMock(),
        cache_service=None,
    )

    monkeypatch.setattr(
        "src.infrastructure.llm.dynamic_llm_factory.Settings",
        lambda: MagicMock(effective_openai_api_key="sk-env-fallback"),
    )

    key1 = _run(factory.resolve_api_key("openai"))
    key2 = _run(factory.resolve_api_key("openai"))

    assert key1 == "sk-env-fallback"
    assert key2 == "sk-env-fallback"
    # 第二次拿 cache，不再戳 DB（env value 也應 cache）
    assert repo_factory.call_count == 1
