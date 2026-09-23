"""SQLAlchemySystemPromptConfigRepository — 平台 singleton（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.platform.entity import SystemPromptConfig
from src.infrastructure.db.models.system_prompt_config_model import (
    SystemPromptConfigModel,
)
from src.infrastructure.db.repositories.system_prompt_config_repository import (
    SQLAlchemySystemPromptConfigRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


def test_system_prompt_get_default_when_not_seeded(session):
    repo = SQLAlchemySystemPromptConfigRepository(session)  # type: ignore[arg-type]
    cfg = _run(repo.get())
    assert "system_prompt_configs.id = 'default'" in session.sql(0)
    assert cfg.id == "default" and cfg.system_prompt == ""


def test_system_prompt_get_and_save(session):
    repo = SQLAlchemySystemPromptConfigRepository(session)  # type: ignore[arg-type]
    session.queue_result([SystemPromptConfigModel(
        id="default", system_prompt="平台規則", updated_at=T0,
    )])
    assert _run(repo.get()).system_prompt == "平台規則"

    _run(repo.save(SystemPromptConfig(system_prompt="新")))
    (added,) = session.added
    assert isinstance(added, SystemPromptConfigModel)
    assert added.system_prompt == "新"

    existing = SystemPromptConfigModel(id="default", system_prompt="舊",
                                       updated_at=T0)
    session.get_result = existing
    _run(repo.save(SystemPromptConfig(system_prompt="改")))
    assert existing.system_prompt == "改"
    assert existing.updated_at > T0
