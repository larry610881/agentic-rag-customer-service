"""SQLAlchemyBillingSettingsRepository — 平台單列設定的讀取與 upsert（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.domain.billing.settings import BILLING_SETTINGS_ID, BillingSettings
from src.infrastructure.db.models.billing_settings_model import BillingSettingsModel
from src.infrastructure.db.repositories.billing_settings_repository import (
    SQLAlchemyBillingSettingsRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyBillingSettingsRepository:
    return SQLAlchemyBillingSettingsRepository(session)  # type: ignore[arg-type]


def test_get_maps_decimal(session, repo):
    assert _run(repo.get()) is None
    session.get_result = BillingSettingsModel(
        id=BILLING_SETTINGS_ID, usd_per_point="0.002", updated_by="a", updated_at=T0
    )
    s = _run(repo.get())
    assert s.usd_per_point == Decimal("0.002")
    assert isinstance(s.usd_per_point, Decimal)
    assert s.updated_by == "a"


def test_save_inserts_singleton_row(session, repo):
    _run(repo.save(BillingSettings(id="ignored", usd_per_point=Decimal("0.01"))))
    (m,) = session.added
    assert m.id == BILLING_SETTINGS_ID  # 永遠是單列
    assert m.usd_per_point == Decimal("0.01")


def test_save_updates_existing(session, repo):
    existing = BillingSettingsModel(
        id=BILLING_SETTINGS_ID, usd_per_point=Decimal("0.001"), updated_at=T0
    )
    session.get_result = existing
    _run(
        repo.save(
            BillingSettings(usd_per_point=Decimal("0.005"), updated_by="root")
        )
    )
    assert existing.usd_per_point == Decimal("0.005")
    assert existing.updated_by == "root"
    assert session.added == []
