"""版本成效（§13.6 層次 1）：打標解析與 metrics use case scoping"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.application.agent.send_message_use_case import SendMessageUseCase
from src.application.prompt_gate.version_use_cases import (
    GetVersionMetricsUseCase,
)
from src.domain.prompt_gate.entity import BotConfigVersion
from src.domain.prompt_gate.metrics import VersionMetrics
from src.domain.prompt_gate.repository import BotConfigVersionRepository
from src.domain.shared.exceptions import EntityNotFoundError


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _uc_with_version_repo(repo):
    return SendMessageUseCase(
        agent_service=AsyncMock(),
        conversation_repository=AsyncMock(),
        config_version_repository=repo,
    )


def test_resolve_current_version_id():
    repo = AsyncMock(spec=BotConfigVersionRepository)
    repo.find_current.return_value = BotConfigVersion(
        id="ver-9", bot_id="b1", is_current=True
    )
    uc = _uc_with_version_repo(repo)
    assert _run(uc._resolve_current_version_id("b1")) == "ver-9"


def test_resolve_current_version_fail_open():
    """版本查詢炸掉不得影響對話主流程（fail-open → None）。"""
    repo = AsyncMock(spec=BotConfigVersionRepository)
    repo.find_current.side_effect = RuntimeError("db down")
    uc = _uc_with_version_repo(repo)
    assert _run(uc._resolve_current_version_id("b1")) is None


def test_resolve_without_repo_or_bot():
    uc = _uc_with_version_repo(None)
    assert _run(uc._resolve_current_version_id("b1")) is None
    repo = AsyncMock(spec=BotConfigVersionRepository)
    uc2 = _uc_with_version_repo(repo)
    assert _run(uc2._resolve_current_version_id(None)) is None
    repo.find_current.assert_not_awaited()


def test_metrics_use_case_tenant_scoped():
    version_repo = AsyncMock(spec=BotConfigVersionRepository)
    version_repo.find_by_id.return_value = None  # 跨租戶 → None
    metrics_repo = AsyncMock()
    uc = GetVersionMetricsUseCase(version_repo, metrics_repo)
    with pytest.raises(EntityNotFoundError):
        _run(uc.execute("t-other", "ver-1"))
    metrics_repo.get_metrics.assert_not_awaited()


def test_metrics_use_case_returns_metrics():
    version_repo = AsyncMock(spec=BotConfigVersionRepository)
    version_repo.find_by_id.return_value = BotConfigVersion(
        id="ver-1", tenant_id="t1", bot_id="b1"
    )
    metrics_repo = AsyncMock()
    metrics_repo.get_metrics.return_value = VersionMetrics(
        version_id="ver-1", message_count=10,
        feedback_up=3, feedback_down=1,
    )
    uc = GetVersionMetricsUseCase(version_repo, metrics_repo)
    m = _run(uc.execute("t1", "ver-1"))
    assert m.message_count == 10
    assert m.feedback_positive_rate == 0.75
