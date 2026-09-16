"""Issue #98 步驟 7：建立型端點的 Idempotency-Key 接線。"""

import asyncio
import inspect
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.shared.idempotency_guard import IdempotencyGuard
from src.domain.shared.idempotency import ClaimOutcome, IdempotencyRecord
from src.interfaces.api import (
    api_key_router,
    bot_router,
    document_router,
    feedback_router,
    prompt_optimizer_run_router,
)
from src.interfaces.api.deps import CurrentTenant
from src.interfaces.api.idempotency import run_idempotent

scenarios("unit/interfaces/idempotent_creates.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class MemoryStore:
    def __init__(self) -> None:
        self.data: dict[str, IdempotencyRecord] = {}

    async def claim(self, key, fingerprint, ttl_seconds):
        if key in self.data:
            return ClaimOutcome(acquired=False, existing=self.data[key])
        self.data[key] = IdempotencyRecord(
            state="in_progress", fingerprint=fingerprint
        )
        return ClaimOutcome(acquired=True)

    async def complete(self, key, record, ttl_seconds):
        self.data[key] = record

    async def release(self, key):
        self.data.pop(key, None)


@pytest.fixture
def ctx():
    return {"calls": 0}


ENDPOINTS = {
    "create_bot": bot_router.create_bot,
    "create_api_key": api_key_router.create_api_key,
    "submit_feedback": feedback_router.submit_feedback,
    "start_run": prompt_optimizer_run_router.start_run,
    "upload_document": document_router.upload_document,
}


@when("檢查五支建立型端點的簽名")
def inspect_signatures(ctx):
    ctx["missing"] = []
    for name, fn in ENDPOINTS.items():
        params = inspect.signature(fn).parameters
        for p in ("idempotency_key", "idempotency_guard"):
            if p not in params:
                ctx["missing"].append(f"{name}.{p}")


@then("每一支都有 idempotency_key 與 idempotency_guard 參數")
def assert_signatures(ctx):
    assert ctx["missing"] == [], ctx["missing"]


def _tenant():
    return CurrentTenant(tenant_id="t1", user_id="u1", role="tenant_admin")


@given("一個記憶體快照 guard 與回傳固定回饋的 SubmitFeedback use case")
def feedback_setup(ctx):
    ctx["guard"] = IdempotencyGuard(MemoryStore())
    feedback = SimpleNamespace(
        id=SimpleNamespace(value="f1"), tenant_id="t1", conversation_id="c1",
        message_id="m1", user_id=None, channel=SimpleNamespace(value="web"),
        rating=SimpleNamespace(value="thumbs_up"), comment=None, tags=[],
        created_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )

    async def execute(command):
        ctx["calls"] += 1
        return feedback

    ctx["uc"] = SimpleNamespace(execute=execute)


@when(parsers.parse('以 key "{key}" 連續呼叫 submit_feedback 兩次'))
def call_feedback_twice(ctx, key):
    body = feedback_router.SubmitFeedbackRequest(
        conversation_id="c1", message_id="m1", channel="web", rating="thumbs_up"
    )
    ctx["responses"] = [
        _run(
            feedback_router.submit_feedback(
                body=body, tenant=_tenant(), use_case=ctx["uc"],
                idempotency_key=key, idempotency_guard=ctx["guard"],
            )
        )
        for _ in range(2)
    ]


@then("兩次狀態碼皆為 201")
def both_201(ctx):
    assert [r.status_code for r in ctx["responses"]] == [201, 201]


@then('第二次標頭 Idempotent-Replayed 為 "true" 且 body 與第一次相同')
def replayed_same(ctx):
    first, second = ctx["responses"]
    assert first.headers["idempotent-replayed"] == "false"
    assert second.headers["idempotent-replayed"] == "true"
    assert json.loads(first.body) == json.loads(second.body)


@then(parsers.parse("SubmitFeedback use case 執行次數為 {n:d}"))
def uc_calls(ctx, n):
    assert ctx["calls"] == n


@given("一個記憶體快照 guard 與回傳固定金鑰的 CreateApiKey use case")
def api_key_setup(ctx):
    ctx["guard"] = IdempotencyGuard(MemoryStore())
    key = SimpleNamespace(
        id="k1", client_id="cid", tenant_id="t1", name="n", description="",
        secret_prefix="ab", scopes=["chat:send"], allowed_bot_ids=[],
        expires_at=None, revoked_at=None, last_used_at=None, created_by="u1",
        is_active=lambda: True,
        created_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )
    ctx["uc"] = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(key=key, client_secret="sec")
        )
    )


@when("不帶 key 呼叫 create_api_key")
def call_api_key_no_key(ctx):
    body = api_key_router.CreateApiKeyRequest(name="n", scopes=["chat:send"])
    ctx["resp"] = _run(
        api_key_router.create_api_key(
            body=body, caller=_tenant(), use_case=ctx["uc"],
            idempotency_key=None, idempotency_guard=ctx["guard"],
        )
    )


@then("回傳的是 ApiKeyCreatedResponse 模型")
def is_model(ctx):
    assert isinstance(ctx["resp"], api_key_router.ApiKeyCreatedResponse)


@given("一個記憶體快照 guard")
def bare_guard(ctx):
    ctx["guard"] = IdempotencyGuard(MemoryStore())


class _M(BaseModel):
    ok: bool = True


@when(parsers.parse('以 status_code {status:d} 與 key "{key}" 呼叫 run_idempotent'))
def call_run(ctx, status, key):
    async def handler():
        return _M()

    ctx["resp"] = _run(
        run_idempotent(
            ctx["guard"], key=key, scope="t1:user:u1:x", fingerprint="fp",
            handler=handler, status_code=status,
        )
    )


@then(parsers.parse('回應狀態碼為 {status:d} 且標頭 Idempotent-Replayed 為 "{v}"'))
def assert_run(ctx, status, v):
    assert ctx["resp"].status_code == status
    assert ctx["resp"].headers["idempotent-replayed"] == v
