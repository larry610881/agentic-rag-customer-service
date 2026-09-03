"""Worker 端點租戶隔離 BDD Step Definitions（Issue #67 fence 掃描新發現）"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.bot.worker_use_cases import (
    DeleteWorkerUseCase,
    UpdateWorkerUseCase,
)
from src.domain.shared.constants import SYSTEM_TENANT_ID
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/security/worker_tenant_isolation.feature")


def _tenant(value: str) -> str | None:
    return SYSTEM_TENANT_ID if value == "SYSTEM" else value


@pytest.fixture(scope="module")
def worker_app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    yield create_app(skip_rate_limit=True)
    mp.undo()


@pytest.fixture
def context():
    return {}


@given("已啟動的 worker 測試應用")
def app_ready(context, worker_app):
    c = worker_app.container
    bots: dict[str, str] = {}

    async def get_bot(bot_id, tenant_id=None, role=None):
        owner = bots.get(bot_id)
        if owner is None:
            raise EntityNotFoundError("Bot", bot_id)
        if role != "system_admin" and owner != tenant_id:
            raise EntityNotFoundError("Bot", bot_id)
        bot = MagicMock()
        bot.tenant_id = owner
        return bot

    get_bot_uc = MagicMock()
    get_bot_uc.execute = AsyncMock(side_effect=get_bot)
    list_uc = AsyncMock()
    list_uc.execute.return_value = []
    worker_repo = AsyncMock()
    worker_repo.find_by_id.return_value = None
    overrides = {
        c.get_bot_use_case: get_bot_uc,
        c.list_workers_use_case: list_uc,
        c.update_worker_use_case: UpdateWorkerUseCase(worker_repo),
        c.delete_worker_use_case: DeleteWorkerUseCase(worker_repo),
    }
    for provider, obj in overrides.items():
        provider.override(providers.Object(obj))
    context.update(
        client=TestClient(worker_app),
        jwt=worker_app.container.jwt_service(),
        bots=bots,
        worker_repo=worker_repo,
        headers={},
        overrides=overrides,
    )
    yield
    for provider in overrides:
        provider.reset_override()


@given(parsers.parse('以角色 "{role}" 租戶 "{tenant}" 的 worker 憑證'))
def credentials(context, role, tenant):
    token = context["jwt"].create_user_token(
        user_id=f"{role}-id", tenant_id=_tenant(tenant), role=role
    )
    context["headers"] = {"Authorization": f"Bearer {token}"}


@given(parsers.parse('bot "{bot_id}" 屬於租戶 "{tenant}"'))
def bot_owner(context, bot_id, tenant):
    context["bots"][bot_id] = tenant


@given(parsers.parse('worker "{worker_id}" 屬於 bot "{bot_id}"'))
def worker_of_bot(context, worker_id, bot_id):
    worker = MagicMock()
    worker.id = worker_id
    worker.bot_id = bot_id
    context["worker_repo"].find_by_id.return_value = worker


_BODY = {"name": "w", "worker_prompt": "p"}


@when(parsers.parse('無憑證列出 bot "{bot_id}" 的 worker'))
def list_anonymous(context, bot_id):
    context["resp"] = context["client"].get(f"/api/v1/bots/{bot_id}/workers")


@when(parsers.parse('請求 worker 端點 "{method}" "{path}"'))
def request_endpoint(context, method, path):
    body = _BODY if method in ("POST", "PUT") else None
    context["resp"] = context["client"].request(
        method, path, json=body, headers=context["headers"]
    )


@then(parsers.parse("worker 回應狀態碼為 {status:d}"))
def status_is(context, status):
    assert context["resp"].status_code == status, context["resp"].text


@then("worker 儲存庫不應被刪除")
def not_deleted(context):
    context["worker_repo"].delete.assert_not_awaited()
