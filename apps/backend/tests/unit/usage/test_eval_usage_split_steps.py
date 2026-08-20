"""Eval Token 用量分流 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

import prompt_optimizer.mutator as mutator_module
from prompt_optimizer.mutator import PromptMutator
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.application.usage.usage_context import resolve_usage_context
from src.domain.rag.value_objects import TokenUsage
from src.domain.usage.repository import UsageRepository

scenarios("unit/usage/eval_usage_split.feature")


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
def saved_records():
    return []


@pytest.fixture
def record_uc(saved_records):
    repo = AsyncMock(spec=UsageRepository)

    async def _save(record):
        saved_records.append(record)

    repo.save.side_effect = _save
    return RecordUsageUseCase(usage_repository=repo)


def _usage(total: int) -> TokenUsage:
    return TokenUsage(
        model="claude-haiku",
        input_tokens=total // 2,
        output_tokens=total - total // 2,
        estimated_cost=0.001,
    )


# ─── 記帳 + 歸因 ───


@when(parsers.parse(
    '以 request_type "{rtype}" 與 run_id "{run_id}" 記帳 {total:d} tokens'
))
def record_with_run_id(record_uc, rtype, run_id, total):
    _run(
        record_uc.execute(
            tenant_id="t1", request_type=rtype,
            usage=_usage(total), run_id=run_id,
        )
    )


@when(parsers.parse(
    '以 request_type "{rtype}" 與 config_version_id "{vid}" 記帳 {total:d} tokens'
))
def record_with_version_id(record_uc, rtype, vid, total):
    _run(
        record_uc.execute(
            tenant_id="t1", request_type=rtype,
            usage=_usage(total), config_version_id=vid,
        )
    )


@when(parsers.parse('以不合法 request_type "{rtype}" 記帳 {total:d} tokens'))
def record_invalid(record_uc, context, rtype, total):
    with pytest.raises(ValueError) as exc_info:
        _run(
            record_uc.execute(
                tenant_id="t1", request_type=rtype, usage=_usage(total),
            )
        )
    context["error"] = exc_info.value


@then(parsers.parse('帳本寫入一筆 request_type 為 "{rtype}" 的記錄'))
def verify_record_type(saved_records, rtype):
    assert len(saved_records) == 1
    assert saved_records[0].request_type == rtype


@then(parsers.parse('該筆記錄的 run_id 為 "{run_id}"'))
def verify_run_id(saved_records, run_id):
    assert saved_records[0].run_id == run_id


@then(parsers.parse('該筆記錄的 config_version_id 為 "{vid}"'))
def verify_version_id(saved_records, vid):
    assert saved_records[0].config_version_id == vid


@then("記帳被拒絕（ValueError）")
def verify_rejected(context, saved_records):
    assert isinstance(context["error"], ValueError)
    assert saved_records == []


# ─── header 解析 ───


@when(parsers.parse(
    '以角色 "{role}" 解析 header 分類 "{category}" 與 run_id "{run_id}"'
))
def resolve_with_header(context, role, category, run_id):
    context["ctx"] = resolve_usage_context(
        category=category, run_id=run_id, role=role
    )


@when(parsers.parse('以角色 "{role}" 解析空 header'))
def resolve_without_header(context, role):
    context["ctx"] = resolve_usage_context(
        category=None, run_id=None, role=role
    )


@then(parsers.parse(
    '解析結果 request_type 為 "{rtype}" 且 run_id 為 "{run_id}"'
))
def verify_ctx_with_run(context, rtype, run_id):
    assert context["ctx"].request_type == rtype
    assert context["ctx"].run_id == run_id


@then(parsers.parse('解析結果 request_type 為 "{rtype}" 且無 run_id'))
def verify_ctx_no_run(context, rtype):
    assert context["ctx"].request_type == rtype
    assert context["ctx"].run_id is None


# ─── mutator 記帳回呼 ───


class _FakeResponse:
    content = "改寫後的 prompt"
    usage_metadata = {
        "input_tokens": 120, "output_tokens": 45, "total_tokens": 165,
    }


class _FakeChatOpenAI:
    def __init__(self, *args, **kwargs):
        pass

    async def ainvoke(self, messages):
        return _FakeResponse()


@given("一個 LLM 回傳固定內容與 usage_metadata 的 PromptMutator")
def mutator_with_callback(context, monkeypatch):
    monkeypatch.setattr(mutator_module, "ChatOpenAI", _FakeChatOpenAI)
    calls: list[tuple[str, dict]] = []

    async def _on_usage(model_name: str, meta: dict) -> None:
        calls.append((model_name, meta))

    context["usage_calls"] = calls
    context["mutator"] = PromptMutator(
        model="gpt-4o-mini", api_key="test", on_usage=_on_usage
    )


@given("一個 usage 回呼必定拋錯的 PromptMutator")
def mutator_with_failing_callback(context, monkeypatch):
    monkeypatch.setattr(mutator_module, "ChatOpenAI", _FakeChatOpenAI)

    async def _on_usage(model_name: str, meta: dict) -> None:
        raise RuntimeError("db down")

    context["mutator"] = PromptMutator(
        model="gpt-4o-mini", api_key="test", on_usage=_on_usage
    )


@when("執行一次 mutate")
def do_mutate(context):
    context["result"] = _run(
        context["mutator"].mutate(
            current_prompt="原始 prompt", failed_cases=[], iteration=1,
        )
    )


@then("usage 回呼收到 model 名稱與 input/output tokens")
def verify_usage_callback(context):
    assert len(context["usage_calls"]) == 1
    model_name, meta = context["usage_calls"][0]
    assert model_name == "gpt-4o-mini"
    assert meta["input_tokens"] == 120
    assert meta["output_tokens"] == 45


@then("mutate 仍回傳改寫後的 prompt")
def verify_mutate_survives(context):
    assert context["result"] == "改寫後的 prompt"
