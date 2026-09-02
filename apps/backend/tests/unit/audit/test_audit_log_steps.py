"""管理端變更稽核 BDD Step Definitions（Issue #60）"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.audit.audit_recorder import AuditRecorder
from src.application.bot.update_bot_use_case import (
    UpdateBotCommand,
    UpdateBotUseCase,
)
from src.application.bot.worker_use_cases import (
    CreateWorkerCommand,
    CreateWorkerUseCase,
    DeleteWorkerUseCase,
    UpdateWorkerCommand,
    UpdateWorkerUseCase,
)
from src.application.platform.system_prompt_use_cases import (
    UpdateSystemPromptsCommand,
    UpdateSystemPromptsUseCase,
)
from src.application.security.guard_rules_use_cases import (
    ResetGuardRulesUseCase,
    UpdateGuardRulesCommand,
    UpdateGuardRulesUseCase,
)
from src.application.tenant.update_tenant_use_case import (
    UpdateTenantCommand,
    UpdateTenantUseCase,
)
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId
from src.domain.platform.entity import SystemPromptConfig
from src.domain.security.guard_config import GuardRulesConfig
from src.domain.tenant.entity import Tenant
from src.domain.tenant.value_objects import TenantId

scenarios("unit/audit/audit_log.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


def _recorder(context, failing=False):
    repo = AsyncMock()
    if failing:
        repo.append = AsyncMock(side_effect=RuntimeError("db down"))
    else:
        repo.append = AsyncMock()
    context["repo"] = repo
    context["audit"] = AuditRecorder(repository=repo)
    return context["audit"]


def _entries(context):
    return [c.args[0] for c in context["repo"].append.await_args_list]


# ── recorder ──


@given("稽核紀錄器與可觀察的 repository")
def recorder(context):
    _recorder(context)


@given("稽核紀錄器且 repository.append 會拋例外")
def failing_recorder(context):
    _recorder(context, failing=True)


@when(parsers.parse(
    '記錄 entity "{etype}" id "{eid}" 由 before {before} 變為 after {after}'
))
def record_change(context, etype, eid, before, after):
    b = json.loads(before)
    a = json.loads(after)
    if a.get("b") == "LONG":
        a["b"] = "x" * 5000
    try:
        _run(context["audit"].record(
            entity_type=etype, entity_id=eid, action="update",
            before=b, after=a, actor_user_id="admin-1", tenant_id="t1",
        ))
        context["error"] = None
    except Exception as e:  # noqa: BLE001
        context["error"] = e


@then(parsers.parse('應寫入 {n:d} 筆稽核且 changed_fields 只含 "{a}" 與 "{b}"'))
def entry_fields(context, n, a, b):
    entries = _entries(context)
    assert len(entries) == n
    assert set(entries[0].changed_fields.keys()) == {a, b}


@then(parsers.parse('"{field}" 的 after 應被截斷至 {limit:d} 字元以內'))
def truncated(context, field, limit):
    entry = _entries(context)[0]
    assert len(entry.changed_fields[field]["after"]) <= limit


@then("不應寫入任何稽核")
def no_entry(context):
    assert context["repo"].append.await_count == 0


@then("不應拋出例外")
def no_error(context):
    assert context["error"] is None


# ── guard ──


@given(parsers.parse("guard 規則目前有 {n:d} 條 input_rules"))
def guard_current(context, n):
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=GuardRulesConfig(
        input_rules=[{"id": f"r{i}", "pattern": "x"} for i in range(n)],
        output_keywords=[],
    ))
    repo.save = AsyncMock()
    context["guard_repo"] = repo


@given("guard 更新用例已注入稽核紀錄器")
def guard_update_uc(context):
    context["uc"] = UpdateGuardRulesUseCase(
        repo=context["guard_repo"], audit=_recorder(context)
    )


@given("guard 重設用例已注入稽核紀錄器")
def guard_reset_uc(context):
    context["uc"] = ResetGuardRulesUseCase(
        repo=context["guard_repo"], audit=_recorder(context)
    )


@when(parsers.parse('管理員 "{actor}" 更新 guard 規則為 {n:d} 條 input_rules'))
def guard_update(context, actor, n):
    _run(context["uc"].execute(UpdateGuardRulesCommand(
        input_rules=[{"id": f"n{i}", "pattern": "y"} for i in range(n)],
        output_keywords=[],
        actor_user_id=actor,
    )))


@when(parsers.parse('管理員 "{actor}" 重設 guard 規則'))
def guard_reset(context, actor):
    _run(context["uc"].execute(actor_user_id=actor))


@then(parsers.parse(
    '應寫入 entity_type "{etype}" action "{action}" actor "{actor}" 的稽核'
))
def entry_matches(context, etype, action, actor):
    entries = _entries(context)
    assert entries, "no audit entries"
    e = entries[-1]
    assert (e.entity_type, e.action, e.actor_user_id) == (etype, action, actor)


@then(parsers.parse('稽核 changed_fields 應含 "{field}"'))
def entry_has_field(context, field):
    assert field in _entries(context)[-1].changed_fields


# ── system prompt ──


@given(parsers.parse('平台 system prompt 目前為 "{text}"'))
def sys_prompt_current(context, text):
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=SystemPromptConfig(system_prompt=text))
    repo.save = AsyncMock()
    context["sys_repo"] = repo


@given("平台 prompt 更新用例已注入稽核紀錄器")
def sys_prompt_uc(context):
    context["uc"] = UpdateSystemPromptsUseCase(
        system_prompt_config_repository=context["sys_repo"],
        audit=_recorder(context),
    )


@when(parsers.parse('管理員 "{actor}" 更新平台 system prompt 為 "{text}"'))
def sys_prompt_update(context, actor, text):
    _run(context["uc"].execute(UpdateSystemPromptsCommand(
        system_prompt=text, actor_user_id=actor,
    )))


# ── bot ──


@given(parsers.parse('一個 base_prompt 為 "{prompt}" 的 bot 與版本 repository'))
def bot_with_version_repo(context, prompt):
    bot = Bot(id=BotId(value="bot-1"), tenant_id="t1", name="b", base_prompt=prompt)
    bot_repo = AsyncMock()
    bot_repo.find_by_id = AsyncMock(return_value=bot)
    bot_repo.save = AsyncMock()
    version_repo = AsyncMock()
    version_repo.next_version_no = AsyncMock(return_value=2)
    version_repo.save = AsyncMock()
    version_repo.set_current = AsyncMock()
    context["bot_repo"] = bot_repo
    context["version_repo"] = version_repo


@given("bot 更新用例已注入稽核紀錄器")
def bot_uc(context):
    context["uc"] = UpdateBotUseCase(
        bot_repository=context["bot_repo"],
        version_repository=context["version_repo"],
        audit=_recorder(context),
    )


@when(parsers.parse('管理員 "{actor}" 將 bot base_prompt 改為 "{prompt}"'))
def bot_update(context, actor, prompt):
    _run(context["uc"].execute(UpdateBotCommand(
        bot_id="bot-1", base_prompt=prompt, actor_user_id=actor,
    )))


@then(parsers.parse('新建的設定版本 author_user_id 應為 "{actor}"'))
def version_author(context, actor):
    version = context["version_repo"].save.await_args.args[0]
    assert version.author_user_id == actor


# ── worker ──


@given("worker 用例已注入稽核紀錄器")
def worker_ucs(context):
    audit = _recorder(context)
    store: dict = {}
    repo = AsyncMock()

    async def _save(w):
        store[w.id] = w

    async def _find(wid):
        return store.get(wid)

    async def _delete(wid):
        store.pop(wid, None)

    repo.save = AsyncMock(side_effect=_save)
    repo.find_by_id = AsyncMock(side_effect=_find)
    repo.delete = AsyncMock(side_effect=_delete)
    context["create_uc"] = CreateWorkerUseCase(repo=repo, audit=audit)
    context["update_uc"] = UpdateWorkerUseCase(repo=repo, audit=audit)
    context["delete_uc"] = DeleteWorkerUseCase(repo=repo, audit=audit)


@when(parsers.parse(
    '管理員 "{actor}" 建立 worker "{name}" 再改 prompt 為 "{prompt}" 再刪除'
))
def worker_lifecycle(context, actor, name, prompt):
    w = _run(context["create_uc"].execute(CreateWorkerCommand(
        bot_id="bot-1", name=name, worker_prompt="原", actor_user_id=actor,
    )))
    _run(context["update_uc"].execute(UpdateWorkerCommand(
        worker_id=w.id, worker_prompt=prompt, actor_user_id=actor,
    )))
    _run(context["delete_uc"].execute(w.id, actor_user_id=actor))


@then(parsers.parse(
    '應依序寫入 entity_type "{etype}" 的 action {actions} 稽核'
))
def worker_entries(context, etype, actions):
    expected = json.loads(f"[{actions}]")
    entries = [e for e in _entries(context) if e.entity_type == etype]
    assert [e.action for e in entries] == expected, [e.action for e in entries]


# ── tenant ──


@given(parsers.parse('租戶 "{tenant_id}" 的 prompt_gate_enabled 為 {value}'))
def tenant_current(context, tenant_id, value):
    tenant = Tenant(id=TenantId(value=tenant_id), name="T")
    tenant.prompt_gate_enabled = value == "true"
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=tenant)
    repo.save = AsyncMock()
    context["tenant_repo"] = repo


@given("租戶更新用例已注入稽核紀錄器")
def tenant_uc(context):
    context["uc"] = UpdateTenantUseCase(
        tenant_repository=context["tenant_repo"], audit=_recorder(context)
    )


@when(parsers.parse(
    '管理員 "{actor}" 將租戶 "{tenant_id}" 的 prompt_gate_enabled 改為 {value}'
))
def tenant_update(context, actor, tenant_id, value):
    _run(context["uc"].execute(UpdateTenantCommand(
        tenant_id=tenant_id, prompt_gate_enabled=(value == "true"),
        actor_user_id=actor,
    )))
