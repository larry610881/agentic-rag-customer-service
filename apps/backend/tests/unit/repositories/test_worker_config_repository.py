"""SQLAlchemyWorkerConfigRepository — bot 範圍查詢、寫入與映射（Issue #101）。

bot_workers 沒有 tenant_id 欄位，歸屬靠 bot_id：呼叫端（worker_use_cases /
require_owned_bot）先驗 bot 歸屬。這裡釘住查詢一定帶 bot_id 條件。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.domain.bot.entity import ToolRagConfig
from src.domain.bot.worker_config import WorkerConfig
from src.infrastructure.db.models.bot_worker_model import BotWorkerModel
from src.infrastructure.db.repositories.worker_config_repository import (
    SQLAlchemyWorkerConfigRepository,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> BotWorkerModel:
    data: dict = {
        "id": "w-1",
        "bot_id": "bot-1",
        "name": "退貨",
        "description": None,
        "worker_prompt": None,
        "llm_provider": None,
        "llm_model": "gpt-x",
        "temperature": 0.2,
        "max_tokens": 256,
        "max_tool_calls": 2,
        "enabled_mcp_ids": None,
        "knowledge_base_ids": ["kb-1"],
        "enabled_tools": None,
        "tool_configs": {"rag_query": {"rerank_enabled": True}},
        "direct_retrieval": None,
        "sort_order": 1,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return BotWorkerModel(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyWorkerConfigRepository:
    return SQLAlchemyWorkerConfigRepository(session)  # type: ignore[arg-type]


def test_find_by_bot_id_scopes_bot_and_maps(session, repo):
    session.queue_result([_model(), _model(id="w-2", enabled_tools=["rag_query"])])
    ws = _run(repo.find_by_bot_id("bot-1"))
    sql = session.sql()
    assert "bot_workers.bot_id = 'bot-1'" in sql
    assert "ORDER BY bot_workers.sort_order" in sql
    first, second = ws
    assert first.description == "" and first.worker_prompt == ""
    assert first.enabled_tools is None  # None = 沿用 bot 設定
    assert first.enabled_mcp_ids == [] and first.knowledge_base_ids == ["kb-1"]
    assert first.direct_retrieval is False
    assert first.tool_configs["rag_query"].rerank_enabled is True
    assert second.enabled_tools == ["rag_query"]


def test_find_by_id(session, repo):
    session.get_result = _model()
    assert _run(repo.find_by_id("w-1")).bot_id == "bot-1"
    session.get_result = None
    assert _run(repo.find_by_id("w-x")) is None


def test_save_new_and_update(session, repo):
    w = WorkerConfig(
        id="w-9",
        bot_id="bot-1",
        name="n",
        tool_configs={"rag_query": ToolRagConfig(rag_top_k=2)},
        direct_retrieval=True,
    )
    _run(repo.save(w))
    (m,) = session.added
    assert (m.bot_id, m.direct_retrieval) == ("bot-1", True)
    assert m.tool_configs == {"rag_query": {"rag_top_k": 2}}

    existing = _model()
    session.get_result = existing
    _run(repo.save(WorkerConfig(id="w-1", bot_id="bot-1", name="改名", sort_order=3)))
    assert (existing.name, existing.sort_order) == ("改名", 3)
    assert existing.tool_configs == {}
    assert existing.updated_at > T0


def test_delete_only_existing(session, repo):
    _run(repo.delete("none"))
    assert session.deleted == []
    m = _model()
    session.get_result = m
    _run(repo.delete("w-1"))
    assert session.deleted == [m]
