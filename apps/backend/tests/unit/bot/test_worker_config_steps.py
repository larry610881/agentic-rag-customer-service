"""BDD steps for Worker Config CRUD."""
import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from unittest.mock import AsyncMock

from src.application.bot.worker_use_cases import (
    CreateWorkerCommand,
    CreateWorkerUseCase,
    DeleteWorkerUseCase,
    ListWorkersUseCase,
    UpdateWorkerCommand,
    UpdateWorkerUseCase,
)
from src.domain.bot.worker_config import WorkerConfig

scenarios("unit/bot/worker_config.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def context():
    return {}


# In-memory fake repository for unit tests
class _InMemoryWorkerRepo:
    def __init__(self):
        self._store: dict[str, WorkerConfig] = {}

    async def save(self, worker: WorkerConfig) -> None:
        self._store[worker.id] = worker

    async def find_by_bot_id(self, bot_id: str) -> list[WorkerConfig]:
        return [
            w for w in self._store.values() if w.bot_id == bot_id
        ]

    async def find_by_id(self, worker_id: str) -> WorkerConfig | None:
        return self._store.get(worker_id)

    async def delete(self, worker_id: str) -> None:
        self._store.pop(worker_id, None)


# ---------- Given ----------

@given("一個 Worker 配置 Repository")
def setup_repo(context):
    context["repo"] = _InMemoryWorkerRepo()


@given(parsers.parse('Bot "{bot_id}" 已有 {count:d} 個 Workers'))
def setup_existing_workers(context, bot_id, count):
    repo = context["repo"]
    for i in range(count):
        w = WorkerConfig(bot_id=bot_id, name=f"Worker {i + 1}")
        _run(repo.save(w))


@given("已建立一個 Worker")
def setup_one_worker(context):
    repo = context["repo"]
    w = WorkerConfig(bot_id="bot-001", name="測試 Worker")
    _run(repo.save(w))
    context["worker_id"] = w.id


# ---------- When ----------

@when(parsers.parse('建立名為 "{name}" 的 Worker 屬於 Bot "{bot_id}"'))
def create_worker(context, name, bot_id):
    uc = CreateWorkerUseCase(repo=context["repo"])
    context["result"] = _run(
        uc.execute(CreateWorkerCommand(bot_id=bot_id, name=name))
    )


@when(parsers.parse('查詢 Bot "{bot_id}" 的 Workers'))
def list_workers(context, bot_id):
    uc = ListWorkersUseCase(repo=context["repo"])
    context["workers_list"] = _run(uc.execute(bot_id))


@when(parsers.parse('更新 Worker 的 llm_model 為 "{model}"'))
def update_worker_model(context, model):
    uc = UpdateWorkerUseCase(repo=context["repo"])
    context["result"] = _run(
        uc.execute(
            UpdateWorkerCommand(
                worker_id=context["worker_id"], llm_model=model,
            )
        )
    )


@when("刪除該 Worker")
def delete_worker(context):
    uc = DeleteWorkerUseCase(repo=context["repo"])
    _run(uc.execute(context["worker_id"]))


@when(parsers.parse(
    '建立 Worker 並指定 enabled_mcp_ids 為 {ids}'
))
def create_worker_with_mcp(context, ids):
    import json

    mcp_ids = json.loads(ids)
    uc = CreateWorkerUseCase(repo=context["repo"])
    context["result"] = _run(
        uc.execute(
            CreateWorkerCommand(
                bot_id="bot-001",
                name="MCP Worker",
                enabled_mcp_ids=mcp_ids,
            )
        )
    )


@when("建立 Worker 並設定 use_rag 為 false")
def create_worker_no_rag(context):
    uc = CreateWorkerUseCase(repo=context["repo"])
    context["result"] = _run(
        uc.execute(
            CreateWorkerCommand(
                bot_id="bot-001",
                name="No RAG Worker",
                use_rag=False,
            )
        )
    )


# ---------- Then ----------

@then(parsers.parse('Worker 應成功建立且名稱為 "{name}"'))
def check_worker_name(context, name):
    assert context["result"].name == name


@then(parsers.parse('Worker 的 bot_id 應為 "{bot_id}"'))
def check_bot_id(context, bot_id):
    assert context["result"].bot_id == bot_id


@then(parsers.parse("應回傳 {count:d} 個 Workers"))
def check_workers_count(context, count):
    assert len(context["workers_list"]) == count


@then(parsers.parse('Worker 的 llm_model 應為 "{model}"'))
def check_llm_model(context, model):
    assert context["result"].llm_model == model


@then("查詢該 Worker 應回傳 None")
def check_deleted(context):
    repo = context["repo"]
    result = _run(repo.find_by_id(context["worker_id"]))
    assert result is None


@then(parsers.parse("Worker 的 enabled_mcp_ids 應包含 {count:d} 個 ID"))
def check_mcp_ids(context, count):
    assert len(context["result"].enabled_mcp_ids) == count


@then("Worker 的 use_rag 應為 false")
def check_no_rag(context):
    assert context["result"].use_rag is False
