"""額度用盡策略 BDD Step Definitions（Issue #74）

domain `decide` 純函式、RecordUsage auto-topup 分支、QuotaPreflightService
（Redis 以 fake 取代）、三通路轉接器（web / widget / LINE）與背景任務入口。
"""

import asyncio
import hashlib
import hmac
import json
from base64 import b64encode
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.billing.quota_preflight import QuotaPreflightService
from src.application.billing.topup_addon_use_case import TopupAddonUseCase
from src.application.knowledge.process_document_use_case import (
    ProcessDocumentUseCase,
)
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.quota.compute_tenant_quota_use_case import TenantQuotaSnapshot
from src.application.tenant.update_tenant_billing_policy_use_case import (
    UpdateTenantBillingPolicyUseCase,
)
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.billing.exhaustion import (
    DEFAULT_BLOCK_MESSAGE,
    QuotaExhaustedError,
    decide,
    resolve_block_message,
)
from src.domain.bot.entity import Bot
from src.domain.knowledge.entity import Document
from src.domain.knowledge.value_objects import DocumentId
from src.domain.ledger.entity import TokenLedger
from src.domain.ledger.topup_entity import REASON_AUTO_TOPUP, TokenLedgerTopup
from src.domain.plan.entity import ExhaustionPolicy, Plan
from src.domain.rag.value_objects import TokenUsage
from src.domain.tenant.entity import Tenant
from src.domain.tenant.value_objects import TenantId
from src.domain.usage.repository import UsageRepository

scenarios("unit/billing/quota_exhaustion_policy.feature")

_T = "t1"
_CHANNEL_SECRET = "line-secret"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FakeRedis:
    """記錄 set 的 TTL 與 delete 的 key；行為同 redis.asyncio 的 get/set/delete。"""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple[str, int | None]] = []
        self.deleted: list[str] = []

    async def get(self, key: str):
        value = self.store.get(key)
        return value.encode() if value is not None else None

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        self.set_calls.append((key, ex))

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.deleted.append(key)


def _snapshot(**overrides) -> TenantQuotaSnapshot:
    base: dict = {
        "tenant_id": _T, "cycle_year_month": "2026-09", "plan_name": "pro",
        "base_total": 1000, "base_remaining": 1000, "addon_remaining": 0,
        "total_remaining": 1000, "total_audit_in_cycle": 0,
        "total_billable_in_cycle": 0, "included_categories": None,
    }
    base.update(overrides)
    return TenantQuotaSnapshot(**base)


@pytest.fixture
def ctx():
    return {"redis": FakeRedis(), "audit": AsyncMock()}


def _preflight(ctx, snapshot: TenantQuotaSnapshot | None = None, *, fail=False):
    compute = MagicMock()
    if fail:
        compute.execute = AsyncMock(side_effect=ConnectionError("db down"))
    else:
        compute.execute = AsyncMock(return_value=snapshot)
    ctx["compute"] = compute
    ctx["preflight"] = QuotaPreflightService(
        compute_quota_factory=lambda: compute, redis_client=ctx["redis"],
    )
    return ctx["preflight"]


# ---------------------------------------------------------------------------
# domain
# ---------------------------------------------------------------------------


@when(parsers.parse(
    '以策略 "{policy}" 剩餘 {remaining:d} 基礎額度 {base:d} 寬限 {grace:d} 判斷'
))
def run_decide(ctx, policy, remaining, base, grace):
    ctx["decision"] = decide(policy, remaining, base, Decimal(grace))


@then("判斷結果為放行")
def decision_allowed(ctx):
    assert ctx["decision"].allowed is True


@then("判斷結果為攔阻")
def decision_blocked(ctx):
    assert ctx["decision"].allowed is False
    assert ctx["decision"].message


@then("判斷結果已套用寬限")
def decision_grace(ctx):
    assert ctx["decision"].grace_applied is True


@when(parsers.re(
    r'以租戶覆寫 "(?P<tenant_override>.*)" 方案文案 "(?P<plan_message>.*)" 解析被擋文案'
))
def resolve_message(ctx, tenant_override, plan_message):
    ctx["message"] = resolve_block_message(
        tenant_override or None, plan_message or None
    )


@then(parsers.parse('解析出的被擋文案為 "{expected}"'))
def message_is(ctx, expected):
    if expected == "平台預設文案":
        expected = DEFAULT_BLOCK_MESSAGE
    assert ctx["message"] == expected


# ---------------------------------------------------------------------------
# auto-topup（RecordUsageUseCase / TopupAddonUseCase）
# ---------------------------------------------------------------------------


@given(parsers.parse(
    '方案 "{name}" 策略 "{policy}" 加購包 {pack:d} tokens 月上限 {cap:d}'
))
def plan_with_policy(ctx, name, policy, pack, cap):
    ctx["plan"] = Plan(
        name=name, base_monthly_tokens=1000, addon_pack_tokens=pack,
        exhaustion_policy=policy, auto_topup_monthly_cap=cap,
    )
    ctx["tenant"] = Tenant(id=TenantId(value=_T), plan=name)


@given(parsers.parse('租戶 "{tenant}" 本月額度已用盡'))
def quota_exhausted(ctx, tenant):
    ctx["quota"] = _snapshot(base_remaining=0, addon_remaining=0, total_remaining=0)


@given(parsers.parse('租戶 "{tenant}" 覆寫策略為 "{policy}"'))
def tenant_override(ctx, tenant, policy):
    ctx["tenant"].exhaustion_policy_override = policy


@given(parsers.parse('租戶 "{tenant}" 本月已自動加購 {count:d} 次'))
def existing_auto_topups(ctx, tenant, count):
    ctx["existing_topups"] = [
        TokenLedgerTopup(tenant_id=tenant, cycle_year_month="2026-09",
                         amount=1000, reason=REASON_AUTO_TOPUP)
        for _ in range(count)
    ]


@when(parsers.parse('租戶 "{tenant}" 記錄一筆用量'))
def record_usage(ctx, tenant):
    usage_repo = AsyncMock(spec=UsageRepository)
    kwargs: dict = {"usage_repository": usage_repo}
    if "plan" in ctx:
        tenant_repo = AsyncMock()
        tenant_repo.find_by_id = AsyncMock(return_value=ctx["tenant"])
        plan_repo = AsyncMock()
        plan_repo.find_by_name = AsyncMock(return_value=ctx["plan"])
        compute = MagicMock()
        compute.execute = AsyncMock(return_value=ctx.get("quota", _snapshot()))
        topup = MagicMock()
        topup.execute = AsyncMock(return_value=None)
        ctx["topup"] = topup
        kwargs.update(
            compute_quota=compute, topup_addon=topup,
            tenant_repository=tenant_repo, plan_repository=plan_repo,
        )
    if "preflight" in ctx:
        kwargs["quota_preflight"] = ctx["preflight"]
    _run(RecordUsageUseCase(**kwargs).execute(
        tenant_id=tenant, request_type="chat_web",
        usage=TokenUsage(model="openai:gpt-5.1", input_tokens=10, output_tokens=10,
                         estimated_cost=0.001),
    ))


@then(parsers.parse("應執行 {count:d} 次自動加購"))
def topup_count(ctx, count):
    assert ctx["topup"].execute.await_count == count


@when(parsers.parse('對租戶 "{tenant}" 執行自動展延'))
def run_topup(ctx, tenant):
    topup_repo = AsyncMock()
    topup_repo.find_in_cycle = AsyncMock(return_value=ctx.get("existing_topups", []))
    ledger_repo = AsyncMock()
    ledger_repo.find_by_tenant_and_cycle = AsyncMock(return_value=TokenLedger(
        id="ledger-1", tenant_id=tenant, cycle_year_month="2026-09",
    ))
    ctx["topup_repo"] = topup_repo
    uc = TopupAddonUseCase(
        topup_repository=topup_repo,
        billing_transaction_repository=AsyncMock(),
        ledger_repository=ledger_repo,
    )
    ctx["topup_result"] = _run(uc.execute(
        tenant_id=tenant, cycle_year_month="2026-09", plan=ctx["plan"],
    ))


@then("不應寫入加購紀錄")
def no_topup_saved(ctx):
    ctx["topup_repo"].save.assert_not_awaited()
    assert ctx["topup_result"] is None


# ---------------------------------------------------------------------------
# 三通路預檢
# ---------------------------------------------------------------------------


@given(parsers.parse('租戶 "{tenant}" 的預檢結果為攔阻，文案 "{message}"'))
def preflight_blocks(ctx, tenant, message):
    _preflight(ctx, _snapshot(
        effective_policy=ExhaustionPolicy.BLOCK, base_remaining=0,
        total_remaining=0, block_message=message,
    ))
    ctx["expected_message"] = message


@given(parsers.parse('租戶 "{tenant}" 的預檢結果為放行'))
def preflight_allows(ctx, tenant):
    _preflight(ctx, _snapshot(effective_policy=ExhaustionPolicy.BLOCK))


def _send_uc(ctx) -> SendMessageUseCase:
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer="ok"))
    uc = SendMessageUseCase(
        agent_service=agent,
        conversation_repository=AsyncMock(),
        bot_repository=AsyncMock(),
        quota_preflight=ctx["preflight"],
    )
    conv = MagicMock()
    conv.id.value = "conv-1"
    conv.messages = []
    conv.metadata = {}
    uc._load_or_create_conversation = AsyncMock(return_value=conv)
    uc._load_bot_config = AsyncMock(return_value={
        "kb_id": "kb-1", "kb_ids": [], "system_prompt": "你是客服",
        "history_limit": 10, "llm_params": {}, "enabled_tools": [], "rag_top_k": 6,
        "rag_score_threshold": 0.0,
        "show_sources": False, "bot_id": "bot-1", "tool_rag_params": None,
        "customer_service_url": "", "mcp_servers": None, "max_tool_calls": 5,
        "router_model": "", "mode": "deep",
    })
    uc._resolve_history = AsyncMock(return_value=(None, "", ""))
    uc._resolve_and_load_memory = AsyncMock(return_value="")
    uc._persist_agent_trace = AsyncMock(return_value=(None, None))
    uc._fire_memory_extraction = AsyncMock()
    uc._resolve_current_version_id = AsyncMock(return_value=None)
    uc._fingerprint_config = AsyncMock(return_value=None)
    ctx["agent"] = agent
    return uc


def _line_bot() -> Bot:
    return Bot(
        tenant_id=_T, name="測試bot", short_code="test01",
        line_channel_secret=_CHANNEL_SECRET, line_channel_access_token="token",
        knowledge_base_ids=["kb1"],
    )


def _signed_body(user_id: str) -> tuple[str, str]:
    body = json.dumps({
        "events": [{
            "type": "message", "replyToken": "rt-1", "timestamp": 1750000000000,
            "source": {"userId": user_id},
            "message": {"type": "text", "text": "你好"},
        }]
    })
    sig = b64encode(
        hmac.new(_CHANNEL_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    ).decode()
    return body, sig


def _line_uc(ctx) -> HandleWebhookUseCase:
    agent = AsyncMock()
    agent.process_message.return_value = AgentResponse(answer="正常回覆")
    line_service = AsyncMock()
    line_service.verify_signature = AsyncMock(return_value=True)
    factory = MagicMock()
    factory.create.return_value = line_service
    bot_repo = AsyncMock()
    bot_repo.find_by_short_code.return_value = _line_bot()
    ctx["agent"] = agent
    ctx["line_service"] = line_service
    return HandleWebhookUseCase(
        agent_service=agent, bot_repository=bot_repo,
        line_service_factory=factory, quota_preflight=ctx["preflight"],
    )


@when(parsers.parse('通路 "{channel}" 的使用者發送訊息'))
def channel_sends(ctx, channel):
    ctx.pop("error", None)
    ctx["channel"] = channel
    if channel == "web":
        uc = _send_uc(ctx)
        try:
            ctx["resp"] = _run(uc.execute(SendMessageCommand(
                tenant_id=_T, message="你好", bot_id="bot-1",
            )))
        except QuotaExhaustedError as e:
            ctx["error"] = e
    elif channel == "widget":
        uc = _send_uc(ctx)

        async def _collect():
            return [e async for e in uc.execute_stream(SendMessageCommand(
                tenant_id=_T, message="你好", bot_id="bot-1",
                identity_source="widget", visitor_id="v1",
            ))]

        ctx["events"] = _run(_collect())
    elif channel == "line":
        uc = _line_uc(ctx)
        body, sig = _signed_body("U1")
        _run(uc.execute_for_bot("test01", body, sig))
    else:  # pragma: no cover
        raise AssertionError(f"unknown channel {channel}")


@then(parsers.parse('通路 "{channel}" 收到固定文案 "{message}"'))
def channel_got_message(ctx, channel, message):
    if channel == "web":
        assert "error" in ctx, "expected QuotaExhaustedError"
        assert ctx["error"].message == message
    elif channel == "widget":
        blocked = [e for e in ctx["events"] if e["type"] == "quota_exhausted"]
        assert blocked and blocked[0]["content"] == message
        assert ctx["events"][-1]["type"] == "done"
    else:
        args = ctx["line_service"].reply_text.await_args
        assert args is not None and args.args[1] == message


@then("不應呼叫 Agent")
def agent_not_called(ctx):
    ctx["agent"].process_message.assert_not_awaited()


@then("應呼叫 Agent")
def agent_called(ctx):
    assert "error" not in ctx
    ctx["agent"].process_message.assert_awaited_once()


# ---------------------------------------------------------------------------
# 背景任務
# ---------------------------------------------------------------------------


@when(parsers.parse('處理租戶 "{tenant}" 的文件 "{doc_id}"'))
def process_document(ctx, tenant, doc_id):
    doc_repo = AsyncMock()
    doc_repo.find_by_id = AsyncMock(return_value=Document(
        id=DocumentId(value=doc_id), tenant_id=tenant, kb_id="kb-1",
        filename="a.txt", content_type="text/plain",
    ))
    file_parser = AsyncMock()
    task_repo = AsyncMock()
    uc = ProcessDocumentUseCase(
        document_repository=doc_repo,
        processing_task_repository=task_repo,
        knowledge_base_repository=AsyncMock(),
        text_splitter_service=MagicMock(),
        embedding_service=AsyncMock(),
        vector_store=AsyncMock(),
        language_detection_service=MagicMock(),
        file_parser_service=file_parser,
        document_file_storage=AsyncMock(),
        quota_preflight=ctx["preflight"],
    )
    _run(uc.execute(doc_id, "task-1"))
    ctx.update(doc_repo=doc_repo, task_repo=task_repo, file_parser=file_parser)


@then(parsers.parse('文件 "{doc_id}" 狀態為 "{status}"'))
def document_status(ctx, doc_id, status):
    statuses = [c.args for c in ctx["doc_repo"].update_status.await_args_list]
    assert (doc_id, status) in statuses, statuses
    task_calls = ctx["task_repo"].update_status.await_args_list
    assert any(
        c.args[1] == "failed"
        and c.kwargs.get("error_message") == ctx["expected_message"]
        for c in task_calls
    ), task_calls


@then("不應解析文件內容")
def parser_not_called(ctx):
    assert not ctx["file_parser"].method_calls


@when(parsers.parse('確認租戶 "{tenant}" 類別 "{category}" 可用'))
def ensure_allowed(ctx, tenant, category):
    ctx.pop("error", None)
    try:
        _run(ctx["preflight"].ensure_allowed(tenant, category))
    except QuotaExhaustedError as e:
        ctx["error"] = e


@then(parsers.parse('應拋出 QuotaExhaustedError 且訊息為 "{message}"'))
def raised_quota_error(ctx, message):
    assert isinstance(ctx.get("error"), QuotaExhaustedError)
    assert ctx["error"].message == message


# ---------------------------------------------------------------------------
# 預檢快取與 fail-open
# ---------------------------------------------------------------------------


@given(parsers.parse('租戶 "{tenant}" 的配額為策略 "{policy}" 剩餘 {remaining:d}'))
def quota_state(ctx, tenant, policy, remaining):
    _preflight(ctx, _snapshot(
        effective_policy=policy, total_remaining=remaining, base_remaining=remaining,
    ))


@given(parsers.parse(
    '租戶 "{tenant}" 的配額為策略 "{policy}" 剩餘 {remaining:d} 且只計入 "{category}"'
))
def quota_state_included(ctx, tenant, policy, remaining, category):
    _preflight(ctx, _snapshot(
        effective_policy=policy, total_remaining=remaining, base_remaining=remaining,
        included_categories=[category],
    ))


@given(parsers.parse('租戶 "{tenant}" 的配額查詢會失敗'))
def quota_fails(ctx, tenant):
    _preflight(ctx, fail=True)


@when(parsers.parse('連續預檢租戶 "{tenant}" 類別 "{category}" {count:d} 次'))
def check_many(ctx, tenant, category, count):
    for _ in range(count):
        ctx["decision"] = _run(ctx["preflight"].check(tenant, category))


@when(parsers.parse('預檢租戶 "{tenant}" 類別 "{category}"'))
def check_once(ctx, tenant, category):
    ctx["decision"] = _run(ctx["preflight"].check(tenant, category))


@then(parsers.parse("配額只計算 {count:d} 次"))
def compute_count(ctx, count):
    assert ctx["compute"].execute.await_count == count


@then(parsers.parse('預檢快取以 {ttl:d} 秒寫入 "{key}"'))
def cache_written(ctx, ttl, key):
    assert (key, ttl) in ctx["redis"].set_calls


@then(parsers.parse('預檢快取 "{key}" 應被清除'))
def cache_deleted(ctx, key):
    assert key in ctx["redis"].deleted


@then(parsers.parse('預檢結果為放行且原因為 "{reason}"'))
def decision_reason(ctx, reason):
    assert ctx["decision"].allowed is True
    assert ctx["decision"].reason == reason


# ---------------------------------------------------------------------------
# 租戶自改策略
# ---------------------------------------------------------------------------


@given(parsers.parse('方案 "{name}" 不允許租戶自改策略'))
def plan_locked(ctx, name):
    ctx["plan"] = Plan(name=name, tenant_may_change_policy=False)
    ctx["tenant"] = Tenant(id=TenantId(value=_T), plan=name)


@given(parsers.parse('方案 "{name}" 允許租戶自改策略'))
def plan_open(ctx, name):
    ctx["plan"] = Plan(name=name, tenant_may_change_policy=True)
    ctx["tenant"] = Tenant(id=TenantId(value=_T), plan=name)


def _policy_uc(ctx) -> UpdateTenantBillingPolicyUseCase:
    tenant_repo = AsyncMock()
    tenant_repo.find_by_id = AsyncMock(return_value=ctx["tenant"])
    plan_repo = AsyncMock()
    plan_repo.find_by_name = AsyncMock(return_value=ctx["plan"])
    ctx["tenant_repo"] = tenant_repo
    return UpdateTenantBillingPolicyUseCase(
        tenant_repository=tenant_repo, plan_repository=plan_repo, audit=ctx["audit"],
    )


def _change_policy(ctx, tenant, policy, role):
    ctx.pop("error", None)
    try:
        ctx["policy_view"] = _run(_policy_uc(ctx).execute(
            tenant_id=tenant, exhaustion_policy=policy, block_message=None,
            actor_role=role, actor_user_id="u1",
        ))
    except PermissionError as e:
        ctx["error"] = e


@when(parsers.parse('租戶管理員將租戶 "{tenant}" 策略改為 "{policy}"'))
def tenant_admin_changes(ctx, tenant, policy):
    _change_policy(ctx, tenant, policy, "tenant_admin")


@when(parsers.parse('系統管理員將租戶 "{tenant}" 策略改為 "{policy}"'))
def system_admin_changes(ctx, tenant, policy):
    _change_policy(ctx, tenant, policy, "system_admin")


@then("應拒絕存取")
def permission_denied(ctx):
    assert isinstance(ctx.get("error"), PermissionError)
    ctx["tenant_repo"].save.assert_not_awaited()


@then(parsers.parse('租戶 "{tenant}" 的策略覆寫為 "{policy}"'))
def policy_saved(ctx, tenant, policy):
    assert "error" not in ctx
    saved = ctx["tenant_repo"].save.await_args.args[0]
    assert saved.exhaustion_policy_override == policy
    assert ctx["policy_view"].effective_policy == policy


@then(parsers.parse('應寫入 "{entity_type}" 稽核紀錄'))
def audit_written(ctx, entity_type):
    assert ctx["audit"].record.await_args.kwargs["entity_type"] == entity_type
