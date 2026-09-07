"""防護階段三層設定 BDD Step Definitions（Issue #75）"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.direct_retrieval_service import DirectRetrievalService
from src.application.agent.guarded_agent_service import GuardedAgentService
from src.application.agent.intent_classifier import ClassifyOutcome
from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.bot.list_bot_audit_logs_use_case import ListBotAuditLogsUseCase
from src.application.bot.update_bot_use_case import UpdateBotCommand, UpdateBotUseCase
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.rag.query_rag_use_case import RetrieveResult
from src.application.security.guard_settings_use_cases import (
    CachedGuardProvider,
    GetEffectiveGuardUseCase,
    GetGuardOverviewUseCase,
    GetTenantGuardUseCase,
    UpdateGuardSettingsUseCase,
)
from src.domain.abuse.policy import NO_ABUSE
from src.domain.agent.entity import AgentResponse
from src.domain.audit.entity import AuditEntry, AuditLogRepository
from src.domain.auth.repository import UserRepository
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.rag.value_objects import Source
from src.domain.security.guard_stages import (
    PLATFORM_SCOPE_ID,
    SCOPE_PLATFORM,
    SCOPE_PROFILE,
    SCOPE_TENANT,
    STAGES,
    GuardSettings,
    GuardSettingsRepository,
    resolve_guard,
    validate_bot_guard_stages,
    validate_guard_overrides,
)
from src.domain.shared.constants import SYSTEM_TENANT_ID
from src.domain.shared.exceptions import ValidationError
from src.infrastructure.auth.in_memory_token_stores import (
    InMemoryRefreshTokenStore,
    InMemoryTokenRevocationStore,
)

scenarios("unit/security/guard_stages.feature")

BLOCKED_TEXT = "您的訊息無法處理"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _stages(text: str) -> list[str]:
    """feature 以 "-" 代表空清單 / None。"""
    return [] if text == "-" else [s.strip() for s in text.split(",") if s.strip()]


class FakeGuardRepo(GuardSettingsRepository):
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], GuardSettings] = {}
        self.reads = 0
        self.fail = False

    async def get(self, scope_kind: str, scope_id: str) -> GuardSettings | None:
        if self.fail:
            raise ConnectionError("db down")
        self.reads += 1
        return self.rows.get((scope_kind, scope_id))

    async def save(self, settings: GuardSettings) -> None:
        self.rows[(settings.scope_kind, settings.scope_id)] = settings

    async def list_profiles(self) -> list[GuardSettings]:
        if self.fail:
            raise ConnectionError("db down")
        return [s for (k, _), s in self.rows.items() if k == SCOPE_PROFILE]


@pytest.fixture
def ctx():
    return {"repo": FakeGuardRepo(), "profiles": {}}


# ---------------------------------------------------------------------------
# domain：解析
# ---------------------------------------------------------------------------


@given(parsers.parse(
    '平台防護設定 stages 為 "{stages}" 且 required_stages 為 "{required}"'
))
def platform_with_required(ctx, stages, required):
    ctx["platform"] = GuardSettings(
        scope_kind=SCOPE_PLATFORM, scope_id=PLATFORM_SCOPE_ID,
        overrides={"stages": _stages(stages), "required_stages": _stages(required)},
    )
    ctx["repo"].rows[(SCOPE_PLATFORM, PLATFORM_SCOPE_ID)] = ctx["platform"]


@given(parsers.parse('平台防護設定 stages 為 "{stages}"'))
def platform_stages(ctx, stages):
    ctx["platform"] = GuardSettings(
        scope_kind=SCOPE_PLATFORM, scope_id=PLATFORM_SCOPE_ID,
        overrides={"stages": _stages(stages)},
    )
    ctx["repo"].rows[(SCOPE_PLATFORM, PLATFORM_SCOPE_ID)] = ctx["platform"]


@given("平台防護設定使用預設值")
def platform_default(ctx):
    ctx["platform"] = None


@given(parsers.parse('方案 "{name}" 的防護覆寫 stages 為 "{stages}"'))
def profile_override(ctx, name, stages):
    ctx["profiles"][name] = {"stages": _stages(stages)}


@given(parsers.parse('租戶 "{tid}" 的防護覆寫 stages 為 "{stages}"'))
def tenant_stages(ctx, tid, stages):
    ctx["tenant"] = GuardSettings(
        scope_kind=SCOPE_TENANT, scope_id=tid, overrides={"stages": _stages(stages)},
    )


@given(parsers.parse(
    '租戶 "{tid}" 指定防護方案 "{profile}" 並覆寫 stages 為 "{stages}" 且被鎖定'
))
def tenant_profile_stages_locked(ctx, tid, profile, stages):
    ctx["tenant"] = GuardSettings(
        scope_kind=SCOPE_TENANT, scope_id=tid,
        overrides={"profile": profile, "stages": _stages(stages), "locked": True},
    )


@given(parsers.parse(
    '租戶 "{tid}" 指定防護方案 "{profile}" 並覆寫 stages 為 "{stages}"'
))
def tenant_profile_stages(ctx, tid, profile, stages):
    ctx["tenant"] = GuardSettings(
        scope_kind=SCOPE_TENANT, scope_id=tid,
        overrides={"profile": profile, "stages": _stages(stages)},
    )


@given(parsers.parse('租戶 "{tid}" 指定防護方案 "{profile}" 且被鎖定'))
def tenant_profile_locked(ctx, tid, profile):
    ctx["tenant"] = GuardSettings(
        scope_kind=SCOPE_TENANT, scope_id=tid,
        overrides={"profile": profile, "locked": True},
    )


@given(parsers.parse('租戶 "{tid}" 指定防護方案 "{profile}"'))
def tenant_profile(ctx, tid, profile):
    ctx["tenant"] = GuardSettings(
        scope_kind=SCOPE_TENANT, scope_id=tid, overrides={"profile": profile},
    )


@when(parsers.parse('解析租戶 "{tid}" 的有效防護（bot 階段為 "{bot_stages}"）'))
def resolve(ctx, tid, bot_stages):
    tenant = ctx.get("tenant")
    if tenant is not None and tenant.scope_id != tid:
        tenant = None
    ctx["effective"] = resolve_guard(
        ctx.get("platform"), tenant, ctx["profiles"],
        bot_stages=None if bot_stages == "-" else _stages(bot_stages),
    )


@then(parsers.parse('有效階段應為 "{stages}"'))
def effective_is(ctx, stages):
    assert list(ctx["effective"].stages) == _stages(stages), ctx["effective"].stages


@then(parsers.parse('階段 "{stage}" 的來源應為 "{source}"'))
def source_is(ctx, stage, source):
    assert ctx["effective"].source_map.get(stage) == source, ctx["effective"].source_map


@then("有效防護應為鎖定狀態")
def effective_locked(ctx):
    assert ctx["effective"].locked is True


@when(parsers.parse('以租戶 "{tid}" 的有效防護驗證 bot 階段 "{stages}"'))
def validate_bot(ctx, tid, stages):
    effective = resolve_guard(ctx.get("platform"), ctx.get("tenant"), ctx["profiles"])
    try:
        validate_bot_guard_stages(_stages(stages), effective)
        ctx["error"] = None
    except ValidationError as e:
        ctx["error"] = e


@when(parsers.parse('以 scope "{scope}" 驗證防護覆寫 {overrides}'))
def validate_scope_overrides(ctx, scope, overrides):
    try:
        validate_guard_overrides(json.loads(overrides), scope)
        ctx["error"] = None
    except ValidationError as e:
        ctx["error"] = e


@then(parsers.parse("防護驗證結果為 {outcome}"))
def validation_outcome(ctx, outcome):
    assert (ctx["error"] is None) == (outcome == "通過"), ctx["error"]


@then(parsers.parse('防護驗證失敗訊息含 "{text}"'))
def validation_message(ctx, text):
    assert ctx["error"] is not None and text in ctx["error"].message, ctx["error"]


# ---------------------------------------------------------------------------
# provider / update use case / audit
# ---------------------------------------------------------------------------


@given("防護設定儲存庫與快取 provider")
def provider(ctx):
    provider = CachedGuardProvider(lambda: ctx["repo"], ttl_seconds=60)
    # 計「provider 真正去 DB 解析」的輪數（寫入用例本身的 get 不算）
    original_load = provider._load
    ctx["loads"] = 0

    async def counting_load(repo, key):
        ctx["loads"] += 1
        return await original_load(repo, key)

    provider._load = counting_load  # type: ignore[method-assign]
    ctx["provider"] = provider
    ctx["audit"] = AsyncMock()


@when(parsers.parse('連續讀取租戶 "{tid}" 的有效防護 {n:d} 次'))
def read_effective(ctx, tid, n):
    for _ in range(n):
        ctx["effective"] = _run(ctx["provider"].effective_for(tid))


@then(parsers.parse("防護儲存庫只被讀取 {n:d} 輪"))
def reads(ctx, n):
    assert ctx["loads"] == n


@when("防護儲存庫失效並清除快取")
def repo_fails(ctx):
    ctx["repo"].fail = True
    ctx["provider"].invalidate()


def _update_uc(ctx) -> UpdateGuardSettingsUseCase:
    return UpdateGuardSettingsUseCase(ctx["repo"], ctx["provider"], audit=ctx["audit"])


@when(parsers.parse('系統管理員將租戶 "{tid}" 的防護覆寫 stages 設為 "{stages}"'))
def admin_updates_tenant(ctx, tid, stages):
    _run(_update_uc(ctx).execute(
        scope_kind=SCOPE_TENANT, scope_id=tid,
        overrides={"stages": _stages(stages)},
        actor_user_id="admin", actor_role="system_admin",
    ))


@when(parsers.parse('系統管理員將平台 required_stages 設為 "{stages}"'))
def admin_updates_platform(ctx, stages):
    _run(_update_uc(ctx).execute(
        scope_kind=SCOPE_PLATFORM, scope_id=PLATFORM_SCOPE_ID,
        overrides={"required_stages": _stages(stages)},
        actor_user_id="admin", actor_role="system_admin",
    ))


@then(parsers.parse(
    '防護稽核應記錄 entity "{entity}"、entity_id "{entity_id}"、'
    'tenant_id "{tenant_id}"、source "{source}"'
))
def audit_recorded(ctx, entity, entity_id, tenant_id, source):
    calls = [c.kwargs for c in ctx["audit"].record.await_args_list]
    assert calls, "audit.record 未被呼叫"
    last = calls[-1]
    assert last["entity_type"] == entity
    assert last["entity_id"] == entity_id
    assert last["tenant_id"] == (None if tenant_id == "-" else tenant_id)
    assert last["source"] == source
    assert last["action"] == "update"


# ---------------------------------------------------------------------------
# #71 租戶端變更紀錄
# ---------------------------------------------------------------------------

_BASE_TIME = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


@given(parsers.parse(
    '機器人 "{bot_id}" 屬於租戶 "{tenant_id}"，'
    '稽核含一筆 bot 變更與一筆平台對 "{target}" 的防護變更'
))
def bot_with_mixed_audit(ctx, bot_id, tenant_id, target):
    bot = Bot(id=BotId(value=bot_id), tenant_id=tenant_id, name="B")
    bot_repo = AsyncMock(spec=BotRepository)
    bot_repo.find_by_id = AsyncMock(return_value=bot)
    bot_entry = AuditEntry(
        id="log-bot", entity_type="bot", entity_id=bot_id, action="update",
        changed_fields={"name": {"before": "A", "after": "B"}},
        actor_user_id="u-1", tenant_id=tenant_id, created_at=_BASE_TIME,
    )
    guard_entry = AuditEntry(
        id="log-guard", entity_type="guard_settings", entity_id=f"tenant:{target}",
        action="update",
        changed_fields={"stages": {"before": [], "after": ["local_classifier"]}},
        actor_user_id="admin", tenant_id=target, source="platform",
        created_at=_BASE_TIME - timedelta(minutes=1),
    )
    audit_repo = AsyncMock(spec=AuditLogRepository)

    async def _find(**kw):
        if kw["entity_type"] == "bot":
            return [bot_entry]
        if kw["entity_type"] == "guard_settings":
            return [guard_entry]
        return []

    audit_repo.find_by_entity = AsyncMock(side_effect=_find)
    user_repo = AsyncMock(spec=UserRepository)
    user_repo.find_by_id = AsyncMock(return_value=None)
    ctx["audit_uc"] = ListBotAuditLogsUseCase(
        bot_repository=bot_repo, audit_log_repository=audit_repo,
        user_repository=user_repo,
    )


@when(parsers.parse('租戶 "{tid}" 的 "{role}" 查詢 "{bot_id}" 的變更紀錄（含防護）'))
def query_audit(ctx, tid, role, bot_id):
    ctx["page"] = _run(ctx["audit_uc"].execute(bot_id, tenant_id=tid, role=role))


@then(parsers.parse(
    '變更紀錄應有 {n:d} 筆，其中 guard_settings 那筆的操作者標籤為 "{label}"'
))
def audit_page(ctx, n, label):
    items = ctx["page"].items
    assert len(items) == n, [i.id for i in items]
    guard_items = [i for i in items if i.entity_type == "guard_settings"]
    assert len(guard_items) == 1
    assert guard_items[0].actor_label == label
    bot_items = [i for i in items if i.entity_type == "bot"]
    assert bot_items[0].actor_label is None


# ---------------------------------------------------------------------------
# 管線（web + LINE 共用 helper）
# ---------------------------------------------------------------------------


def _sources(score):
    return [Source(
        document_name="FAQ", content_snippet="板橋店 2 樓設有快剪",
        score=score, chunk_id="c-1",
    )]


def _guard_mock():
    guard = AsyncMock()
    guard.check_input = AsyncMock(return_value=SimpleNamespace(passed=True))
    guard.check_output = AsyncMock(return_value=SimpleNamespace(passed=True))
    guard.block_by_classifier = AsyncMock(return_value=SimpleNamespace(
        passed=False, blocked_response=BLOCKED_TEXT, rule_matched="intent_attack",
    ))
    return guard


def _abuse_mock():
    abuse = AsyncMock()
    abuse.evaluate = AsyncMock(return_value=NO_ABUSE)
    abuse.record = AsyncMock(return_value=NO_ABUSE)
    return abuse


def _classifier_mock(is_attack: bool):
    classifier = AsyncMock()
    classifier.classify_sanitize = AsyncMock(return_value=ClassifyOutcome(
        worker=None, query="", is_attack=is_attack,
    ))
    return classifier


def _spy_trace(ctx, uc):
    original = uc._persist_agent_trace

    async def spy(**kwargs):
        trace_id, nodes = await original(**kwargs)
        ctx["trace_nodes"] = nodes or []
        return trace_id, nodes

    uc._persist_agent_trace = spy


def _setup_bot(ctx, *, mode: str, is_attack: bool):
    ctx["bot"] = Bot(
        id=BotId(value="bot-1"), tenant_id="t1", name="B", base_prompt="p",
        knowledge_base_ids=["kb-1"], mode=mode,
        line_channel_secret="s", line_channel_access_token="t",
    )
    ctx["guard"] = _guard_mock()
    ctx["abuse"] = _abuse_mock()
    ctx["classifier"] = _classifier_mock(is_attack)
    ctx["provider"] = CachedGuardProvider(lambda: ctx["repo"], ttl_seconds=60)
    query_rag = AsyncMock()
    query_rag.retrieve = AsyncMock(return_value=RetrieveResult(
        chunks=["板橋店 2 樓設有快剪"], sources=_sources(0.9),
    ))
    ctx["direct"] = DirectRetrievalService(query_rag_use_case=query_rag)
    worker_repo = AsyncMock()
    worker_repo.find_by_bot_id = AsyncMock(return_value=[])
    ctx["worker_repo"] = worker_repo


@given("一個 kb 模式的 bot，分類器對訊息的判定為攻擊")
def kb_bot_attack(ctx):
    _setup_bot(ctx, mode="kb", is_attack=True)


@given("一個 deep 模式且沒有 worker 的 bot")
def deep_bot(ctx):
    _setup_bot(ctx, mode="deep", is_attack=False)


def _web_uc(ctx) -> SendMessageUseCase:
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer="答"))
    ctx["agent"] = agent
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = None
    bot_repo = AsyncMock()
    bot_repo.find_by_id.return_value = ctx["bot"]
    sys_repo = AsyncMock()
    sys_repo.get.return_value = SimpleNamespace(system_prompt="系統")
    uc = SendMessageUseCase(
        agent_service=agent,
        conversation_repository=conv_repo,
        bot_repository=bot_repo,
        system_prompt_config_repository=sys_repo,
        intent_classifier=ctx["classifier"],
        worker_config_repo=ctx["worker_repo"],
        direct_retrieval_service=ctx["direct"],
        prompt_guard=ctx["guard"],
        abuse_control=ctx["abuse"],
        guard_provider=ctx["provider"],
    )
    _spy_trace(ctx, uc)
    return uc


def _line_uc(ctx) -> HandleWebhookUseCase:
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer="答"))
    ctx["agent"] = agent
    bot_repo = AsyncMock()
    bot_repo.find_by_short_code = AsyncMock(return_value=ctx["bot"])
    line_service = AsyncMock()
    line_service.verify_signature = AsyncMock(return_value=True)
    ctx["line_service"] = line_service
    factory = MagicMock()
    factory.create = MagicMock(return_value=line_service)
    return HandleWebhookUseCase(
        agent_service=agent, bot_repository=bot_repo, line_service_factory=factory,
        direct_retrieval_service=ctx["direct"],
        intent_classifier=ctx["classifier"],
        worker_config_repo=ctx["worker_repo"],
        prompt_guard=ctx["guard"],
        abuse_control=ctx["abuse"],
        guard_provider=ctx["provider"],
    )


@when(parsers.parse('以 "{channel}" 通路送出訊息'))
def send_via(ctx, channel):
    ctx["channel"] = channel
    if channel == "web":
        cmd = SendMessageCommand(
            tenant_id="t1", bot_id="bot-1", message="板橋店有快剪嗎",
            visitor_id="v-1", identity_source="widget",
        )
        ctx["response"] = _run(_web_uc(ctx).execute(cmd))
        return
    body = json.dumps({"events": [{
        "type": "message", "replyToken": "tok", "source": {"userId": "U1"},
        "message": {"type": "text", "text": "板橋店有快剪嗎"},
        "timestamp": 1700000000000, "webhookEventId": "evt-guard-1",
    }]})
    _run(_line_uc(ctx).execute_for_bot("shop", body, "sig"))


@then(parsers.parse("分類器應被以無 worker 方式呼叫 {n:d} 次"))
def classifier_attack_only_calls(ctx, n):
    calls = ctx["classifier"].classify_sanitize.await_args_list
    assert len(calls) == n, calls
    for c in calls:
        assert c.kwargs.get("workers") == []
        assert c.kwargs.get("attack_only") is True


def _reply_text(ctx) -> str:
    if ctx["channel"] == "web":
        return ctx["response"].answer
    call = ctx["line_service"].reply_with_quick_reply.call_args
    return call.args[1]


@then(parsers.parse('通路回覆應為 "{result}"'))
def reply_is(ctx, result):
    text = _reply_text(ctx)
    if result == "攔截":
        assert text == BLOCKED_TEXT, text
        ctx["agent"].process_message.assert_not_awaited()
    else:
        assert text == "答", text


@then(parsers.parse("輸入正則防護被呼叫 {i:d} 次、異常計分被呼叫 {a:d} 次"))
def stage_call_counts(ctx, i, a):
    assert ctx["guard"].check_input.await_count == i
    assert ctx["abuse"].record.await_count == a
    if a == 0:
        ctx["abuse"].evaluate.assert_not_awaited()


@then(parsers.parse("Agent 收到的階段清單含 output_guard 為 {value}"))
def agent_metadata_stages(ctx, value):
    kwargs = ctx["agent"].process_message.call_args.kwargs
    stages = kwargs["metadata"]["_guard_stages"]
    assert ("output_guard" in stages) is (value == "true"), stages


@then(parsers.parse("輸出防護被呼叫 {n:d} 次"))
def output_guard_calls(ctx, n):
    assert ctx["guard"].check_output.await_count == n


@then(parsers.parse('trace 應含 "{node_type}" 節點且其階段含 "{stage}"'))
def trace_has_guard_node(ctx, node_type, stage):
    nodes = [n for n in ctx.get("trace_nodes", []) if n.get("node_type") == node_type]
    assert nodes, [n.get("node_type") for n in ctx.get("trace_nodes", [])]
    meta = nodes[0].get("metadata") or {}
    assert stage in meta.get("stages", []), nodes[0]
    assert meta.get("sources"), nodes[0]


# ---------------------------------------------------------------------------
# 咽喉點
# ---------------------------------------------------------------------------


@given("一個包了 prompt guard 的咽喉點 agent service")
def throat(ctx):
    inner = AsyncMock()
    inner.process_message = AsyncMock(return_value=AgentResponse(answer="答"))
    ctx["guard"] = _guard_mock()
    ctx["throat"] = GuardedAgentService(inner=inner, prompt_guard=ctx["guard"])


@when(parsers.parse('以階段清單 "{stages}" 呼叫咽喉點'))
def call_throat(ctx, stages):
    ctx["guard"].check_input.reset_mock()
    ctx["guard"].check_output.reset_mock()
    _run(ctx["throat"].process_message(
        tenant_id="t1", kb_id="kb-1", user_message="hi",
        metadata={"_guard_stages": _stages(stages)},
    ))


@then(parsers.parse("咽喉點的輸入防護被呼叫 {i:d} 次、輸出防護被呼叫 {o:d} 次"))
def throat_counts(ctx, i, o):
    assert ctx["guard"].check_input.await_count == i
    assert ctx["guard"].check_output.await_count == o


# ---------------------------------------------------------------------------
# bot 儲存
# ---------------------------------------------------------------------------


@given("一個既有 bot 的更新用例（帶防護 provider）")
def bot_update_uc(ctx):
    bot = Bot(id=BotId(value="bot-m"), tenant_id="t1", name="M")
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=bot)
    repo.save = AsyncMock()
    ctx["bot_uc"] = UpdateBotUseCase(
        bot_repository=repo, guard_provider=ctx["provider"]
    )


@when(parsers.parse('將 bot guard_stages 更新為 "{stages}"'))
def update_bot_stages(ctx, stages):
    try:
        _run(ctx["bot_uc"].execute(
            UpdateBotCommand(bot_id="bot-m", guard_stages=_stages(stages))
        ))
        ctx["outcome"] = "saved"
    except ValidationError:
        ctx["outcome"] = "error"


@then(parsers.parse("bot 更新結果應為 {outcome}"))
def bot_update_outcome(ctx, outcome):
    assert ctx["outcome"] == outcome


# ---------------------------------------------------------------------------
# API 授權（create_app + override）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def guard_app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    yield create_app(skip_rate_limit=True)
    mp.undo()


@given("已啟動的防護設定測試應用")
def app_ready(ctx, guard_app):
    c = guard_app.container
    repo = ctx["repo"]
    provider = CachedGuardProvider(lambda: repo, ttl_seconds=60)
    bot_repo = AsyncMock(spec=BotRepository)
    bot_repo.find_by_id = AsyncMock(
        return_value=Bot(id=BotId(value="bot-1"), tenant_id="t1", name="B")
    )
    overrides = {
        c.get_guard_overview_use_case: GetGuardOverviewUseCase(repo),
        c.get_tenant_guard_use_case: GetTenantGuardUseCase(repo),
        c.update_guard_settings_use_case: UpdateGuardSettingsUseCase(
            repo, provider, audit=AsyncMock()
        ),
        c.get_effective_guard_use_case: GetEffectiveGuardUseCase(bot_repo, provider),
        c.token_revocation_store: InMemoryTokenRevocationStore(),
        c.refresh_token_store: InMemoryRefreshTokenStore(),
    }
    for prov, obj in overrides.items():
        prov.override(providers.Object(obj))
    ctx.update(client=TestClient(guard_app), jwt=c.jwt_service())
    yield
    for prov in overrides:
        prov.reset_override()


@given(parsers.parse('以租戶 "{tenant}" 角色 "{role}" 的防護憑證'))
def credentials(ctx, tenant, role):
    tid = SYSTEM_TENANT_ID if tenant == "SYSTEM" else tenant
    token = ctx["jwt"].create_user_token(f"{role}-id", tid, role)
    ctx["headers"] = {"Authorization": f"Bearer {token}"}


_BODIES = {
    "/api/v1/admin/guard/settings/platform": {
        "overrides": {"stages": list(STAGES[:4])},
    },
    "/api/v1/admin/guard/settings/profiles/exhibition": {
        "overrides": {"stages": ["regex_input", "output_guard", "abuse_scoring"]},
    },
    "/api/v1/admin/guard/settings/tenants/t1": {
        "profile": "exhibition", "overrides": {"stages": ["classifier_attack"]},
        "locked": False,
    },
}


@when(parsers.parse('請求防護端點 "{method}" "{path}"'))
def request_guard(ctx, method, path):
    body = _BODIES.get(path) if method in ("POST", "PUT") else None
    ctx["resp"] = ctx["client"].request(
        method, path, json=body, headers=ctx["headers"]
    )


@then(parsers.parse("防護端點回應狀態碼為 {status:d}"))
def guard_status(ctx, status):
    assert ctx["resp"].status_code == status, ctx["resp"].text


@then("有效防護回應含 stages、required、locked 與 source_map")
def effective_payload(ctx):
    data = ctx["resp"].json()
    assert set(data["stages"]) >= set(data["required"])
    assert isinstance(data["locked"], bool)
    assert set(data["source_map"]) == set(data["stages"])
    assert data["bot_stages"] is None
    assert data["available_stages"] == list(STAGES)
