"""萃取對話記憶 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.memory.extract_memory_use_case import (
    ExtractMemoryCommand,
    ExtractMemoryUseCase,
)
from src.domain.memory.entity import MemoryFact
from src.domain.memory.repository import MemoryFactRepository
from src.domain.memory.services import ExtractedFact, MemoryExtractionService
from src.domain.memory.value_objects import MemoryFactId

scenarios("unit/memory/extract_memory.feature")


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
    repo = AsyncMock(spec=MemoryFactRepository)
    repo.find_by_profile = AsyncMock(return_value=[])
    repo.upsert_by_key = AsyncMock()
    return repo


@pytest.fixture
def mock_extraction_service():
    return AsyncMock(spec=MemoryExtractionService)


@pytest.fixture
def use_case(mock_fact_repo, mock_extraction_service):
    return ExtractMemoryUseCase(
        memory_fact_repository=mock_fact_repo,
        extraction_service=mock_extraction_service,
    )


# --- Given ---


@given(parsers.parse('訪客 Profile "{profile_id}" 沒有既有記憶'))
def no_existing_memory(context, mock_fact_repo, profile_id):
    context["profile_id"] = profile_id
    mock_fact_repo.find_by_profile = AsyncMock(return_value=[])


@given(parsers.parse("LLM 萃取服務會回傳 {count:d} 筆事實"))
def llm_returns_n_facts(context, mock_extraction_service, count):
    sample_facts = [
        ExtractedFact(
            category="preference",
            key="偏好配送方式",
            value="冷凍配送",
            confidence=0.9,
        ),
        ExtractedFact(
            category="personal_info",
            key="姓名",
            value="Alice",
            confidence=1.0,
        ),
    ]
    mock_extraction_service.extract_facts = AsyncMock(
        return_value=sample_facts[:count]
    )


@given("LLM 萃取服務回傳空陣列")
def llm_returns_empty(context, mock_extraction_service):
    mock_extraction_service.extract_facts = AsyncMock(return_value=[])


@given(
    parsers.parse(
        '訪客 Profile "{profile_id}" 已有記憶 key "{key}" value "{value}"'
    )
)
def existing_memory_fact(context, mock_fact_repo, profile_id, key, value):
    context["profile_id"] = profile_id
    existing = MemoryFact(
        id=MemoryFactId(),
        profile_id=profile_id,
        tenant_id="t-001",
        key=key,
        value=value,
    )
    mock_fact_repo.find_by_profile = AsyncMock(return_value=[existing])


@given("LLM 萃取服務會回傳偏好配送方式為冷凍配送")
def llm_returns_delivery_pref(context, mock_extraction_service):
    facts = [
        ExtractedFact(
            category="preference",
            key="偏好配送方式",
            value="冷凍配送",
            confidence=0.9,
        ),
    ]
    mock_extraction_service.extract_facts = AsyncMock(return_value=facts)


# --- When ---


@when("萃取對話記憶")
def extract_memory(context, use_case):
    profile_id = context.get("profile_id", "p-001")
    command = ExtractMemoryCommand(
        profile_id=profile_id,
        tenant_id="t-001",
        conversation_id="conv-001",
        messages=[
            {"role": "user", "content": "我想要冷凍配送"},
            {"role": "assistant", "content": "好的，已為您記錄偏好"},
        ],
    )
    context["result"] = _run(use_case.execute(command))


# --- Then ---


@then(parsers.parse("應 upsert {count:d} 筆記憶事實"))
def should_upsert_count(context, mock_fact_repo, count):
    assert context["result"] == count
    assert mock_fact_repo.upsert_by_key.call_count == count


@then(parsers.parse('記憶 "{key}" 的值應為 "{value}"'))
def memory_value_check(context, mock_fact_repo, key, value):
    for c in mock_fact_repo.upsert_by_key.call_args_list:
        fact = c[0][0] if c[0] else c[1].get("fact")
        if fact.key == key:
            assert fact.value == value
            return
    pytest.fail(f"No fact with key '{key}' was upserted")
