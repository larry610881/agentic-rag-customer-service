"""異常控管設定三層 BDD Step Definitions（Issue #68 P7c）"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.abuse.abuse_control_service import AbuseControlService
from src.application.abuse.abuse_settings_use_cases import (
    CachedAbusePolicyProvider,
    GetAbuseSettingsOverviewUseCase,
    GetTenantAbuseSettingsUseCase,
    ListAbuseControlsUseCase,
    ReleaseAbuseControlUseCase,
    UpdateAbuseSettingsUseCase,
)
from src.domain.abuse.policy import AbusePolicy, AbuseSubject, SubjectKind
from src.domain.abuse.settings import (
    PLATFORM_SCOPE_ID,
    SCOPE_PLATFORM,
    SCOPE_PROFILE,
    SCOPE_TENANT,
    AbuseSettings,
    AbuseSettingsRepository,
    resolve_policy,
    validate_overrides,
)
from src.domain.shared.constants import SYSTEM_TENANT_ID
from src.domain.shared.exceptions import ValidationError
from src.infrastructure.abuse.in_memory_abuse_score_store import (
    InMemoryAbuseScoreStore,
)
from src.infrastructure.auth.in_memory_token_stores import (
    InMemoryRefreshTokenStore,
    InMemoryTokenRevocationStore,
)

scenarios("unit/abuse/abuse_settings.feature")


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeSettingsRepo(AbuseSettingsRepository):
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], AbuseSettings] = {}
        self.reads = 0
        self.fail = False

    async def get(self, scope_kind: str, scope_id: str) -> AbuseSettings | None:
        if self.fail:
            raise ConnectionError("db down")
        self.reads += 1
        return self.rows.get((scope_kind, scope_id))

    async def save(self, settings: AbuseSettings) -> None:
        self.rows[(settings.scope_kind, settings.scope_id)] = settings

    async def list_profiles(self) -> list[AbuseSettings]:
        if self.fail:
            raise ConnectionError("db down")
        return [s for (k, _), s in self.rows.items() if k == SCOPE_PROFILE]


@pytest.fixture
def ctx():
    return {"repo": FakeSettingsRepo()}


# ---------------------------------------------------------------------------
# domain
# ---------------------------------------------------------------------------


@when(parsers.parse('驗證覆寫 "{key}" 為 {value}'))
def validate_one(ctx, key, value):
    try:
        ctx["clean"] = validate_overrides({key: json.loads(value)})
        ctx["error"] = None
    except ValidationError as e:
        ctx["error"] = e


@when(parsers.parse("驗證覆寫組 threshold_l1 {a:d} threshold_l2 {b:d}"))
def validate_pair(ctx, a, b):
    try:
        validate_overrides({"threshold_l1": a, "threshold_l2": b})
        ctx["error"] = None
    except ValidationError as e:
        ctx["error"] = e


@then(parsers.parse("驗證結果為 {outcome}"))
def validation_outcome(ctx, outcome):
    assert (ctx["error"] is None) == (outcome == "通過"), ctx["error"]


@then(parsers.parse('驗證失敗訊息含 "{text}"'))
def validation_message(ctx, text):
    assert ctx["error"] is not None and text in ctx["error"].message


@given(parsers.parse('平台覆寫 mode "{mode}" threshold_l1 {t1:d}'))
def platform_override(ctx, mode, t1):
    ctx["platform"] = AbuseSettings(
        scope_kind=SCOPE_PLATFORM, scope_id=PLATFORM_SCOPE_ID,
        overrides={"mode": mode, "threshold_l1": t1},
    )


@given(parsers.parse('租戶 "{tid}" 指定方案 "{profile}" 並微調 duration_l3 {d:d}'))
def tenant_override(ctx, tid, profile, d):
    ctx["tenant"] = AbuseSettings(
        scope_kind=SCOPE_TENANT, scope_id=tid,
        overrides={"profile": profile, "duration_l3": d},
    )


@when(parsers.parse('解析租戶 "{tid}" 的生效政策'))
def resolve(ctx, tid):
    tenant = ctx.get("tenant")
    if tenant is not None and tenant.scope_id != tid:
        tenant = None
    ctx["policy"] = resolve_policy(ctx.get("platform"), tenant)


@then(parsers.parse(
    '生效政策 mode 為 "{mode}"、threshold_l1 為 {t1:g}、'
    'threshold_l3 為 {t3:g}、duration_l3 為 {d:d}'
))
def policy_is(ctx, mode, t1, t3, d):
    p = ctx["policy"]
    assert p.mode.value == mode
    assert p.thresholds[1] == t1 and p.thresholds[3] == t3
    assert p.durations[3] == d


# ---------------------------------------------------------------------------
# provider / use cases
# ---------------------------------------------------------------------------


@given("設定儲存庫（會被讀取次數計數）與快取 provider")
def provider(ctx):
    ctx["provider"] = CachedAbusePolicyProvider(lambda: ctx["repo"], ttl_seconds=60)
    ctx["audit"] = AsyncMock()


@when(parsers.parse('連續讀取租戶 "{tid}" 的政策 {n:d} 次'))
def read_policy(ctx, tid, n):
    for _ in range(n):
        ctx["policy"] = _run(ctx["provider"].policy_for(tid))


@then(parsers.parse("儲存庫只被讀取 {n:d} 輪"))
def reads(ctx, n):
    assert ctx["repo"].reads == n * 2  # platform + tenant 各一次


@when("設定儲存庫失效並清除快取")
def repo_fails(ctx):
    ctx["repo"].fail = True
    ctx["provider"].invalidate()


@then("讀到的政策為預設 enforce")
def default_policy(ctx):
    assert ctx["policy"].mode.value == "enforce"
    assert ctx["policy"].thresholds == AbusePolicy().thresholds


@when(parsers.parse(
    '系統管理員把租戶 "{tid}" 設為方案 "{profile}" 並微調 mode "{mode}"'
))
def update_tenant(ctx, tid, profile, mode):
    uc = UpdateAbuseSettingsUseCase(ctx["repo"], ctx["provider"], audit=ctx["audit"])
    ctx["provider"]._cache[tid] = (AbusePolicy(), 10**12)  # 先塞快取以驗證清除
    try:
        _run(uc.execute(
            scope_kind=SCOPE_TENANT, scope_id=tid, overrides={"mode": mode},
            actor_user_id="admin", profile=profile,
        ))
        ctx["error"] = None
    except ValidationError as e:
        ctx["error"] = e


@then(parsers.parse('儲存的租戶覆寫含 profile "{profile}" 與 mode "{mode}"'))
def stored_overrides(ctx, profile, mode):
    row = ctx["repo"].rows[(SCOPE_TENANT, "t1")]
    assert row.overrides == {"mode": mode, "profile": profile}


@then(parsers.parse('稽核應記錄 "{entity}" 的 "{action}"'))
def audit_recorded(ctx, entity, action):
    calls = [c.kwargs for c in ctx["audit"].record.await_args_list]
    assert any(c["entity_type"] == entity and c["action"] == action for c in calls)


@then("快取已清除")
def cache_cleared(ctx):
    assert "t1" not in ctx["provider"]._cache


@then(parsers.parse('更新失敗訊息含 "{text}"'))
def update_failed(ctx, text):
    assert ctx["error"] is not None and text in ctx["error"].message


@given(parsers.parse('分數儲存中租戶 "{tid}" 的訪客 "{vid}" 鎖定在等級 {level:d}'))
def locked_visitor(ctx, tid, vid, level):
    store = ctx.setdefault("store", InMemoryAbuseScoreStore())
    _run(store.set_level(AbuseSubject(SubjectKind.VISITOR, vid).key(tid), level, 600))


@when(parsers.parse('列出租戶 "{tid}" 的受控主體'))
def list_controls(ctx, tid):
    ctx["controls"] = _run(ListAbuseControlsUseCase(ctx["store"]).execute(tid))


@then(parsers.parse('受控清單有 {n:d} 筆，等級 {level:d}，遮罩為 "{masked}"'))
def controls_listed(ctx, n, level, masked):
    rows = ctx["controls"]
    assert len(rows) == n and rows[0].level == level
    assert rows[0].subject_masked == masked


# ---------------------------------------------------------------------------
# API 授權（create_app + override）
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def settings_app():
    mp = pytest.MonkeyPatch()
    mp.setenv("E2E_MODE", "true")
    mp.setenv("OPENAI_API_KEY", "sk-test-fake")
    from src.main import create_app

    yield create_app(skip_rate_limit=True)
    mp.undo()


@given("已啟動的異常控管設定測試應用")
def app_ready(ctx, settings_app):
    c = settings_app.container
    repo = ctx["repo"]
    store = ctx.setdefault("store", InMemoryAbuseScoreStore())
    provider = CachedAbusePolicyProvider(lambda: repo, ttl_seconds=60)
    control = AbuseControlService(store, provider, audit=AsyncMock())
    overrides = {
        c.get_abuse_settings_overview_use_case: GetAbuseSettingsOverviewUseCase(repo),
        c.get_tenant_abuse_settings_use_case: GetTenantAbuseSettingsUseCase(repo),
        c.update_abuse_settings_use_case: UpdateAbuseSettingsUseCase(
            repo, provider, audit=AsyncMock()
        ),
        c.list_abuse_controls_use_case: ListAbuseControlsUseCase(store),
        c.release_abuse_control_use_case: ReleaseAbuseControlUseCase(control),
        c.token_revocation_store: InMemoryTokenRevocationStore(),
        c.refresh_token_store: InMemoryRefreshTokenStore(),
    }
    for prov, obj in overrides.items():
        prov.override(providers.Object(obj))
    ctx.update(
        client=TestClient(settings_app), jwt=c.jwt_service(), overrides=overrides
    )
    yield
    for prov in overrides:
        prov.reset_override()


@given(parsers.parse('以租戶 "{tenant}" 角色 "{role}" 的設定憑證'))
def credentials(ctx, tenant, role):
    tid = SYSTEM_TENANT_ID if tenant == "SYSTEM" else tenant
    token = ctx["jwt"].create_user_token(f"{role}-id", tid, role)
    ctx["headers"] = {"Authorization": f"Bearer {token}"}


_BODIES = {
    "/api/v1/admin/abuse/settings/platform": {"overrides": {"mode": "monitor"}},
    "/api/v1/admin/abuse/settings/tenants/t1": {
        "profile": "strict", "overrides": {"mode": "monitor"},
    },
    "/api/v1/admin/abuse/controls/release": {
        "tenant_id": "t1", "subject_kind": "visitor", "subject_id": "v1",
    },
}


@when(parsers.parse('請求設定端點 "{method}" "{path}"'))
def request_settings(ctx, method, path):
    body = _BODIES.get(path) if method in ("POST", "PUT") else None
    ctx["resp"] = ctx["client"].request(
        method, path, json=body, headers=ctx["headers"]
    )


@then(parsers.parse("設定端點回應狀態碼為 {status:d}"))
def settings_status(ctx, status):
    assert ctx["resp"].status_code == status, ctx["resp"].text


@then(parsers.parse("回應 editable 為 {value}"))
def editable_is(ctx, value):
    assert ctx["resp"].json()["editable"] is (value == "true")


@then(parsers.parse('受控清單回應不含 "{raw}" 且含 "{masked}"'))
def controls_masked(ctx, raw, masked):
    text = ctx["resp"].text
    assert raw not in text and masked in text
