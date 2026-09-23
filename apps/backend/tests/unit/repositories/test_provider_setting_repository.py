"""SQLAlchemyProviderSettingRepository — 平台供應商設定（全域表）（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.platform.entity import ProviderSetting
from src.domain.platform.model_registry import DEFAULT_MODELS
from src.domain.platform.value_objects import (
    ModelConfig,
    ProviderName,
    ProviderSettingId,
    ProviderType,
)
from src.infrastructure.db.models.provider_setting_model import (
    ProviderSettingModel,
)
from src.infrastructure.db.repositories.provider_setting_repository import (
    SQLAlchemyProviderSettingRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> ProviderSettingModel:
    data: dict = {
        "id": "ps-1",
        "provider_type": "llm",
        "provider_name": "openai",
        "display_name": "OpenAI",
        "is_enabled": True,
        "api_key_encrypted": "enc:xxx",
        "base_url": "",
        "models": [
            {"model_id": "gpt-x", "display_name": "GPT X", "input_price": 1.0}
        ],
        "extra_config": None,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return ProviderSettingModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyProviderSettingRepository:
    return SQLAlchemyProviderSettingRepository(session)  # type: ignore[arg-type]


def test_find_by_id_maps_models_and_keeps_key_encrypted(session, repo):
    session.queue_result([_model()])
    s = _run(repo.find_by_id("ps-1"))
    assert "provider_settings.id = 'ps-1'" in session.sql()
    assert s is not None
    assert s.provider_type is ProviderType.LLM
    assert s.api_key_encrypted == "enc:xxx"
    (m,) = s.models
    assert (m.model_id, m.is_enabled, m.input_price) == ("gpt-x", True, 1.0)
    assert s.extra_config == {}
    assert _run(repo.find_by_id("none")) is None


def test_empty_models_backfill_from_registry(session, repo):
    session.queue_result([_model(provider_name="deepseek", models=[])])
    s = _run(repo.find_by_id("ps-1"))
    expected = [m["model_id"] for m in DEFAULT_MODELS["deepseek"]["llm"]]
    assert [m.model_id for m in s.models] == expected


def test_find_by_type_and_name_and_lists(session, repo):
    session.queue_result([_model()])
    _run(repo.find_by_type_and_name(ProviderType.LLM, ProviderName.OPENAI))
    sql = session.sql()
    assert "provider_settings.provider_type = 'llm'" in sql
    assert "provider_settings.provider_name = 'openai'" in sql
    assert _run(repo.find_by_type_and_name(ProviderType.LLM, ProviderName.QWEN)) is None

    session.queue_result([_model(), _model(id="ps-2")])
    assert len(_run(repo.find_all_by_type(ProviderType.EMBEDDING))) == 2
    assert "provider_settings.provider_type = 'embedding'" in session.sql()

    assert _run(repo.find_all()) == []


def _setting(**over) -> ProviderSetting:
    data: dict = {
        "id": ProviderSettingId(value="ps-1"),
        "display_name": "新名",
        "api_key_encrypted": "enc:new",
        "models": [ModelConfig(model_id="m", display_name="M", is_default=True)],
    }
    data.update(over)
    return ProviderSetting(**data)


def test_save_new_and_update(session, repo):
    _run(repo.save(_setting()))
    (m,) = session.added
    assert m.api_key_encrypted == "enc:new"
    assert m.models[0]["model_id"] == "m" and m.models[0]["is_default"] is True

    existing = _model()
    session.get_result = existing
    _run(repo.save(_setting(is_enabled=False)))
    assert existing.display_name == "新名"
    assert existing.is_enabled is False
    assert existing.api_key_encrypted == "enc:new"


def test_delete_only_when_exists(session, repo):
    _run(repo.delete("none"))
    assert session.deleted == []
    existing = _model()
    session.get_result = existing
    _run(repo.delete("ps-1"))
    assert session.deleted == [existing]
