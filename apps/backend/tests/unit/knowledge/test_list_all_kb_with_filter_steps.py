"""知識庫/Bot 列表租戶篩選 BDD Step Definitions"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.bot.list_all_bots_use_case import ListAllBotsUseCase
from src.application.knowledge.list_all_knowledge_bases_use_case import (
    ListAllKnowledgeBasesUseCase,
)
from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.value_objects import BotId, BotShortCode
from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.value_objects import KnowledgeBaseId

scenarios("unit/knowledge/list_all_kb_with_filter.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _make_kb(tenant_id: str, name: str) -> KnowledgeBase:
    return KnowledgeBase(
        id=KnowledgeBaseId(),
        tenant_id=tenant_id,
        name=name,
        description="",
        document_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_bot(tenant_id: str, name: str) -> Bot:
    return Bot(
        id=BotId(),
        short_code=BotShortCode(),
        tenant_id=tenant_id,
        name=name,
        description="",
        is_active=True,
        system_prompt="",
        knowledge_base_ids=[],
        llm_params=BotLLMParams(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# --- Given ---


@given("系統中有 3 個不同租戶的知識庫")
def setup_kbs(context):
    kbs = [
        _make_kb("t-001", "KB-A"),
        _make_kb("t-002", "KB-B"),
        _make_kb("t-003", "KB-C"),
    ]
    mock_repo = AsyncMock()
    mock_repo.find_all = AsyncMock(return_value=kbs)
    mock_repo.find_all_by_tenant = AsyncMock(
        side_effect=lambda tid: [kb for kb in kbs if kb.tenant_id == tid]
    )
    context["kb_use_case"] = ListAllKnowledgeBasesUseCase(
        knowledge_base_repository=mock_repo,
    )
    context["all_kbs"] = kbs


@given("系統中有 2 個不同租戶的 Bot")
def setup_bots(context):
    bots = [
        _make_bot("t-001", "Bot-A"),
        _make_bot("t-002", "Bot-B"),
    ]
    mock_repo = AsyncMock()
    mock_repo.find_all = AsyncMock(return_value=bots)
    mock_repo.find_all_by_tenant = AsyncMock(
        side_effect=lambda tid: [b for b in bots if b.tenant_id == tid]
    )
    context["bot_use_case"] = ListAllBotsUseCase(bot_repository=mock_repo)
    context["all_bots"] = bots


# --- When ---


@when("我列出所有知識庫但不指定 tenant_id")
def list_all_kbs(context):
    context["result"] = _run(context["kb_use_case"].execute())


@when(parsers.parse('我列出所有知識庫並指定 tenant_id 為 "{tid}"'))
def list_kbs_by_tenant(context, tid):
    context["result"] = _run(context["kb_use_case"].execute(tenant_id=tid))


@when("我列出所有 Bot 但不指定 tenant_id")
def list_all_bots(context):
    context["result"] = _run(context["bot_use_case"].execute())


@when(parsers.parse('我列出所有 Bot 並指定 tenant_id 為 "{tid}"'))
def list_bots_by_tenant(context, tid):
    context["result"] = _run(context["bot_use_case"].execute(tenant_id=tid))


# --- Then ---


@then(parsers.parse("應回傳全部 {count:d} 個知識庫"))
def verify_all_kbs(context, count):
    assert len(context["result"]) == count


@then(parsers.parse('應只回傳 tenant_id 為 "{tid}" 的知識庫'))
def verify_filtered_kbs(context, tid):
    assert all(kb.tenant_id == tid for kb in context["result"])
    assert len(context["result"]) == 1


@then(parsers.parse("應回傳全部 {count:d} 個 Bot"))
def verify_all_bots(context, count):
    assert len(context["result"]) == count


@then(parsers.parse('應只回傳 tenant_id 為 "{tid}" 的 Bot'))
def verify_filtered_bots(context, tid):
    assert all(b.tenant_id == tid for b in context["result"])
    assert len(context["result"]) == 1
