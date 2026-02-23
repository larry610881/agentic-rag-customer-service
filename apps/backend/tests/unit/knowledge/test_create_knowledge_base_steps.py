"""建立知識庫 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge.create_knowledge_base_use_case import (
    CreateKnowledgeBaseCommand,
    CreateKnowledgeBaseUseCase,
)
from src.application.knowledge.list_knowledge_bases_use_case import (
    ListKnowledgeBasesUseCase,
)
from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.value_objects import KnowledgeBaseId

scenarios("unit/knowledge/create_knowledge_base.feature")


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
    repo.save = AsyncMock()

    def _find_all_by_tenant(tid):
        return [kb for kb in all_kbs if kb.tenant_id == tid]

    repo.find_all_by_tenant = AsyncMock(side_effect=_find_all_by_tenant)
    return repo


@pytest.fixture
def create_use_case(mock_kb_repo):
    return CreateKnowledgeBaseUseCase(knowledge_base_repository=mock_kb_repo)


@pytest.fixture
def list_use_case(mock_kb_repo):
    return ListKnowledgeBasesUseCase(knowledge_base_repository=mock_kb_repo)


@given(parsers.parse('租戶 "{tenant_id}" 已存在'))
def tenant_exists(context, tenant_id):
    context["tenant_id"] = tenant_id


@given(parsers.parse('租戶 "{tenant_id}" 有知識庫 "{kb_name}"'))
def tenant_has_kb(all_kbs, tenant_id, kb_name):
    kb = KnowledgeBase(
        id=KnowledgeBaseId(),
        tenant_id=tenant_id,
        name=kb_name,
        description="",
    )
    all_kbs.append(kb)


@when(
    parsers.parse(
        '我為租戶 "{tenant_id}" 建立名稱為 "{name}" 描述為 "{desc}" 的知識庫'
    )
)
def create_kb(context, create_use_case, tenant_id, name, desc):
    command = CreateKnowledgeBaseCommand(
        tenant_id=tenant_id,
        name=name,
        description=desc,
    )
    context["result"] = _run(create_use_case.execute(command))


@when(parsers.parse('我列出租戶 "{tenant_id}" 的所有知識庫'))
def list_kbs(context, list_use_case, tenant_id):
    context["result_list"] = _run(list_use_case.execute(tenant_id))


@then("知識庫應成功建立")
def kb_created(context):
    assert context["result"] is not None


@then(parsers.parse('知識庫名稱應為 "{name}"'))
def kb_name_is(context, name):
    assert context["result"].name == name


@then(parsers.parse('知識庫應綁定租戶 "{tenant_id}"'))
def kb_bound_to_tenant(context, tenant_id):
    assert context["result"].tenant_id == tenant_id


@then(parsers.parse("應只回傳 {count:d} 個知識庫"))
def kb_count_is(context, count):
    assert len(context["result_list"]) == count


@then(parsers.parse('回傳的知識庫名稱應包含 "{name}"'))
def kb_list_contains_name(context, name):
    names = [kb.name for kb in context["result_list"]]
    assert name in names
