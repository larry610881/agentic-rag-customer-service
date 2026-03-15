"""載入用戶記憶 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.memory.load_memory_use_case import (
    LoadMemoryCommand,
    LoadMemoryUseCase,
)
from src.domain.memory.entity import MemoryFact
from src.domain.memory.repository import MemoryFactRepository
from src.domain.memory.value_objects import MemoryFactId

scenarios("unit/memory/load_memory.feature")


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
def mock_fact_repo():
    return AsyncMock(spec=MemoryFactRepository)


@pytest.fixture
def use_case(mock_fact_repo):
    return LoadMemoryUseCase(memory_fact_repository=mock_fact_repo)


# --- Given ---


@given(parsers.parse('訪客 Profile "{profile_id}" 有 {count:d} 筆記憶事實'))
def profile_has_facts(context, mock_fact_repo, profile_id, count):
    context["profile_id"] = profile_id
    facts = [
        MemoryFact(
            id=MemoryFactId(),
            profile_id=profile_id,
            tenant_id="t-001",
            key="偏好配送方式",
            value="冷凍配送",
        ),
        MemoryFact(
            id=MemoryFactId(),
            profile_id=profile_id,
            tenant_id="t-001",
            key="姓名",
            value="Alice",
        ),
    ]
    mock_fact_repo.find_by_profile = AsyncMock(return_value=facts[:count])


@given(parsers.parse('訪客 Profile "{profile_id}" 沒有任何記憶'))
def profile_no_memory(context, mock_fact_repo, profile_id):
    context["profile_id"] = profile_id
    mock_fact_repo.find_by_profile = AsyncMock(return_value=[])


@given(parsers.parse('訪客 Profile "{profile_id}" 有一筆已過期的記憶'))
def profile_expired_memory(context, mock_fact_repo, profile_id):
    context["profile_id"] = profile_id
    # Repository filters expired by default, so return empty
    mock_fact_repo.find_by_profile = AsyncMock(return_value=[])


# --- When ---


@when(parsers.parse('載入 Profile "{profile_id}" 的記憶'))
def load_memory(context, use_case, profile_id):
    command = LoadMemoryCommand(profile_id=profile_id)
    context["result"] = _run(use_case.execute(command))


# --- Then ---


@then(parsers.parse('記憶 prompt 應包含 "{text}"'))
def prompt_contains(context, text):
    assert text in context["result"].formatted_prompt


@then(parsers.parse('記憶 prompt 應以 "{prefix}" 開頭'))
def prompt_starts_with(context, prefix):
    assert context["result"].formatted_prompt.startswith(prefix)


@then("記憶 context 應為空")
def context_is_empty(context):
    assert context["result"].formatted_prompt == ""


@then(parsers.parse("has_memory 應為 {value}"))
def has_memory_check(context, value):
    expected = value.lower() == "true"
    assert context["result"].has_memory == expected
