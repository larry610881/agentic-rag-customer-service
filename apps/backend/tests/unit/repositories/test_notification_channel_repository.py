"""SQLAlchemyNotificationChannelRepository（Issue #101）。

平台層級設定、無租戶欄位；守住 config 以加密字串原樣映射。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.observability.notification import NotificationChannel
from src.infrastructure.db.models.notification_channel_model import (
    NotificationChannelModel,
)
from src.infrastructure.db.repositories.notification_channel_repository import (
    SQLAlchemyNotificationChannelRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> NotificationChannelModel:
    data: dict = {
        "id": "ch-1",
        "channel_type": "teams",
        "name": "值班",
        "enabled": True,
        "config_encrypted": "enc:xxx",
        "throttle_minutes": 15,
        "min_severity": "all",
        "notify_diagnostics": True,
        "diagnostic_severity": "critical",
        "notify_abuse": True,
        "notify_config_change": False,
        "updated_at": T0,
        "created_at": T0,
    }
    data.update(over)
    return NotificationChannelModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyNotificationChannelRepository:
    return SQLAlchemyNotificationChannelRepository(session)  # type: ignore[arg-type]


def test_get_by_id_maps_entity_keeping_config_encrypted(session, repo):
    assert _run(repo.get_by_id("x")) is None
    session.queue_result([_model()])
    ch = _run(repo.get_by_id("ch-1"))
    assert "notification_channels.id = 'ch-1'" in session.sql(-1)
    assert ch is not None
    assert ch.channel_type == "teams"
    assert ch.config_encrypted == "enc:xxx"  # 不在 repo 解密
    assert ch.notify_diagnostics is True


def test_list_all_and_list_enabled(session, repo):
    session.queue_result([_model()])
    assert len(_run(repo.list_all())) == 1
    _run(repo.list_enabled())
    assert "notification_channels.enabled IS true" in session.sql(-1)


def test_save_new_and_existing(session, repo):
    ch = NotificationChannel(id="ch-9", channel_type="email", name="n",
                             config_encrypted="enc:y")
    assert _run(repo.save(ch)) is ch
    (added,) = session.added
    assert isinstance(added, NotificationChannelModel)
    assert added.config_encrypted == "enc:y"

    existing = _model()
    session.get_result = existing
    _run(repo.save(NotificationChannel(id="ch-1", channel_type="slack", name="改",
                                       enabled=False, config_encrypted="enc:z")))
    assert existing.channel_type == "slack"
    assert existing.enabled is False
    assert existing.config_encrypted == "enc:z"
    assert existing.updated_at > T0


def test_delete_reports_rowcount(session, repo):
    session.queue_result(rowcount=1)
    assert _run(repo.delete("ch-1")) is True
    assert "notification_channels.id = 'ch-1'" in session.sql(0)
    assert _run(repo.delete("ch-x")) is False
