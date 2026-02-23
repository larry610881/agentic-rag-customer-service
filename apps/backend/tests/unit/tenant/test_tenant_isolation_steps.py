"""租戶資料隔離 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.list_knowledge_bases_use_case import (
    ListKnowledgeBasesUseCase,
)
from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.value_objects import KnowledgeBaseId

scenarios("unit/tenant/tenant_isolation.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def all_kbs():
    """Shared list to accumulate knowledge bases across steps."""
    return []


@pytest.fixture
def mock_kb_repo(all_kbs):
    repo = AsyncMock()

    def _find_all_by_tenant(tid):
        return [kb for kb in all_kbs if kb.tenant_id == tid]

    repo.find_all_by_tenant = AsyncMock(side_effect=_find_all_by_tenant)
    return repo


@pytest.fixture
def list_use_case(mock_kb_repo):
    return ListKnowledgeBasesUseCase(knowledge_base_repository=mock_kb_repo)


@given(parsers.parse('租戶 "{tenant_id}" 有知識庫 "{kb_name}"'))
def tenant_has_kb(all_kbs, tenant_id, kb_name):
    kb = KnowledgeBase(
        id=KnowledgeBaseId(),
        tenant_id=tenant_id,
        name=kb_name,
        description="",
    )
    all_kbs.append(kb)


@when(parsers.parse('我以租戶 "{tenant_id}" 身分列出知識庫'))
def list_kbs_as_tenant(context, list_use_case, tenant_id):
    context["result_list"] = _run(list_use_case.execute(tenant_id))


@then(parsers.parse("應只回傳 {count:d} 個知識庫"))
def kb_count_is(context, count):
    assert len(context["result_list"]) == count


@then(parsers.parse('回傳的知識庫名稱應包含 "{name}"'))
def kb_list_contains_name(context, name):
    names = [kb.name for kb in context["result_list"]]
    assert name in names


@then(parsers.parse('回傳的知識庫名稱不應包含 "{name}"'))
def kb_list_not_contains_name(context, name):
    names = [kb.name for kb in context["result_list"]]
    assert name not in names
