"""SQLAlchemyGuardRulesConfigRepository — 平台 singleton 防護規則（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.security.guard_config import GuardRulesConfig
from src.infrastructure.db.models.guard_rules_config_model import (
    GuardRulesConfigModel,
)
from src.infrastructure.db.repositories.guard_rules_config_repository import (
    SQLAlchemyGuardRulesConfigRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


def test_guard_rules_get_maps_row(session):
    repo = SQLAlchemyGuardRulesConfigRepository(session)  # type: ignore[arg-type]
    assert _run(repo.get()) is None
    assert "guard_rules_configs.id = 'default'" in session.sql(0)
    session.queue_result([GuardRulesConfigModel(
        id="default", input_rules=None, output_keywords=[{"k": "密碼"}],
        llm_guard_enabled=True, llm_input_guard_enabled=True,
        llm_guard_model="m", input_guard_prompt="ip", output_guard_prompt="op",
        blocked_response="擋", created_at=T0, updated_at=T0,
    )])
    cfg = _run(repo.get())
    assert cfg is not None
    assert cfg.input_rules == []
    assert cfg.output_keywords == [{"k": "密碼"}]
    assert cfg.llm_guard_enabled is True and cfg.llm_input_guard_enabled is True
    assert (cfg.input_guard_prompt, cfg.output_guard_prompt) == ("ip", "op")
    assert cfg.blocked_response == "擋"


def test_guard_rules_save_merges(session):
    repo = SQLAlchemyGuardRulesConfigRepository(session)  # type: ignore[arg-type]
    _run(repo.save(GuardRulesConfig(input_rules=[{"p": "ignore"}],
                                    llm_input_guard_enabled=True)))
    (merged,) = session.merged
    assert isinstance(merged, GuardRulesConfigModel)
    assert merged.id == "default"
    assert merged.input_rules == [{"p": "ignore"}]
    assert merged.llm_input_guard_enabled is True
    assert session.commits == 1
