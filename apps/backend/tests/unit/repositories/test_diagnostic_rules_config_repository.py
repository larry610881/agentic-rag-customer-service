"""SQLAlchemyDiagnosticRulesConfigRepository — 平台 singleton（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.observability.rule_config import DiagnosticRulesConfig
from src.infrastructure.db.models.diagnostic_rules_config_model import (
    DiagnosticRulesConfigModel,
)
from src.infrastructure.db.repositories.diagnostic_rules_config_repository import (
    SQLAlchemyDiagnosticRulesConfigRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


def test_diagnostic_get_reads_default_row(session):
    repo = SQLAlchemyDiagnosticRulesConfigRepository(session)  # type: ignore[arg-type]
    assert _run(repo.get()) is None
    assert "diagnostic_rules_configs.id = 'default'" in session.sql(0)
    session.queue_result([DiagnosticRulesConfigModel(
        id="default", single_rules=None, combo_rules=[{"a": 1}], updated_at=T0,
    )])
    cfg = _run(repo.get())
    assert cfg is not None
    assert cfg.single_rules == [] and cfg.combo_rules == [{"a": 1}]


def test_diagnostic_save_and_delete(session):
    repo = SQLAlchemyDiagnosticRulesConfigRepository(session)  # type: ignore[arg-type]
    _run(repo.save(DiagnosticRulesConfig(single_rules=[{"r": 1}])))
    (added,) = session.added
    assert isinstance(added, DiagnosticRulesConfigModel)
    assert added.single_rules == [{"r": 1}]

    existing = DiagnosticRulesConfigModel(id="default", single_rules=[],
                                          combo_rules=[], updated_at=T0)
    session.get_result = existing
    _run(repo.save(DiagnosticRulesConfig(single_rules=[{"r": 2}],
                                         combo_rules=[{"c": 1}])))
    assert existing.single_rules == [{"r": 2}]
    assert existing.combo_rules == [{"c": 1}]
    assert existing.updated_at > T0

    _run(repo.delete())
    assert session.deleted == [existing]
    session.get_result = None
    _run(repo.delete())
    assert len(session.deleted) == 1
