"""BDD steps — 租戶端 Bot 變更紀錄可見性（Issue #71；Issue #77 併入 worker 列）"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.audit.audit_recorder import AuditRecorder
from src.application.bot.list_bot_audit_logs_use_case import (
    BotAuditLogPage,
    ListBotAuditLogsUseCase,
)
from src.application.bot.worker_use_cases import (
    CreateWorkerCommand,
    CreateWorkerUseCase,
    DeleteWorkerUseCase,
    UpdateWorkerCommand,
    UpdateWorkerUseCase,
)
from src.domain.audit.entity import AuditEntry, AuditLogRepository, encode_audit_cursor
from src.domain.auth.entity import User
from src.domain.auth.repository import UserRepository
from src.domain.auth.value_objects import Email, UserId
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.bot.worker_config import WorkerConfig
from src.domain.bot.worker_repository import WorkerConfigRepository
from src.domain.shared.exceptions import EntityNotFoundError

scenarios("unit/bot/bot_audit_visibility.feature")

_BASE_TIME = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    bot_repo = AsyncMock(spec=BotRepository)
    bot_repo.find_by_id = AsyncMock(return_value=None)
    audit_repo = AsyncMock(spec=AuditLogRepository)
    audit_repo.find_by_entity = AsyncMock(return_value=[])
    audit_repo.find_by_entity_or_parent = AsyncMock(return_value=[])
    user_repo = AsyncMock(spec=UserRepository)
    user_repo.find_by_id = AsyncMock(return_value=None)
    worker_repo = AsyncMock(spec=WorkerConfigRepository)
    worker_repo.find_by_bot_id = AsyncMock(return_value=[])
    return {
        "bot_repo": bot_repo,
        "audit_repo": audit_repo,
        "user_repo": user_repo,
        "worker_repo": worker_repo,
        "entries": [],
        "bots": {},
    }


def _entry(
    bot_id: str,
    changed_fields: dict,
    *,
    actor: str | None = "u-001",
    seq: int = 0,
) -> AuditEntry:
    return AuditEntry(
        id=f"log-{seq}",
        entity_type="bot",
        entity_id=bot_id,
        action="update",
        changed_fields=changed_fields,
        actor_user_id=actor,
        tenant_id="t-001",
        created_at=_BASE_TIME - timedelta(minutes=seq),
    )


def _worker_entry(
    bot_id: str,
    worker_id: str,
    changed_fields: dict,
    *,
    action: str = "update",
    seq: int = 0,
) -> AuditEntry:
    """Issue #77：worker 稽核列帶 tenant_id 與 parent=bot。"""
    return AuditEntry(
        id=f"wlog-{seq}",
        entity_type="worker",
        entity_id=worker_id,
        action=action,
        changed_fields=changed_fields,
        actor_user_id="u-001",
        tenant_id="t-001",
        parent_entity_type="bot",
        parent_entity_id=bot_id,
        created_at=_BASE_TIME - timedelta(minutes=seq, seconds=30),
    )


def _add_entry(context, entry: AuditEntry) -> None:
    """entity=bot ∪ parent=bot 走 find_by_entity_or_parent；
    guard 列走 find_by_entity。"""
    context["entries"].append(entry)

    def _union(**kw):
        rows = [
            e for e in context["entries"]
            if (e.entity_type == kw["entity_type"] and e.entity_id == kw["entity_id"])
            or (
                e.parent_entity_type == kw["parent_entity_type"]
                and e.parent_entity_id == kw["parent_entity_id"]
            )
        ]
        rows.sort(key=lambda e: (e.created_at, e.id), reverse=True)
        return rows[: kw["limit"]]

    def _single(**kw):
        rows = [
            e for e in context["entries"]
            if e.entity_type == kw["entity_type"] and e.entity_id == kw["entity_id"]
        ]
        return rows[: kw["limit"]]

    context["audit_repo"].find_by_entity_or_parent = AsyncMock(side_effect=_union)
    context["audit_repo"].find_by_entity = AsyncMock(side_effect=_single)


# ── Given ──


@given(parsers.parse('機器人 "{bot_id}" 屬於租戶 "{tenant_id}"'))
def setup_bot(context, bot_id, tenant_id):
    bot = Bot(id=BotId(value=bot_id), tenant_id=tenant_id, name="Test Bot")
    context["bots"][bot_id] = bot
    context["bot_repo"].find_by_id = AsyncMock(
        side_effect=lambda bid: context["bots"].get(bid)
    )


@given(
    parsers.parse(
        '稽核紀錄有一筆 "{bot_id}" 的 update，由使用者 "{actor}" '
        '將 "{field}" 從 "{before}" 改為 "{after}"'
    )
)
def setup_scalar_entry(context, bot_id, actor, field, before, after):
    _add_entry(
        context,
        _entry(bot_id, {field: {"before": before, "after": after}}, actor=actor),
    )


@given(parsers.parse('使用者 "{user_id}" 的 email 為 "{email}"'))
def setup_user(context, user_id, email):
    user = User(
        id=UserId(user_id), tenant_id="t-001", email=Email(email),
    )
    context["user_repo"].find_by_id = AsyncMock(
        side_effect=lambda uid: user if uid == user_id else None
    )


@given(
    parsers.parse(
        '稽核紀錄有一筆 "{bot_id}" 的 update，llm_params 由 temperature {t0}、'
        "max_tokens {m0:d} 改為 temperature {t1}、max_tokens {m1:d}"
    )
)
def setup_llm_params_entry(context, bot_id, t0, m0, t1, m1):
    _add_entry(
        context,
        _entry(
            bot_id,
            {
                "llm_params": {
                    "before": {"temperature": float(t0), "max_tokens": m0},
                    "after": {"temperature": float(t1), "max_tokens": m1},
                }
            },
        ),
    )


@given(
    parsers.parse(
        '稽核紀錄有一筆 "{bot_id}" 的 update，將 "{field}" 從 {n0:d} 字改為 {n1:d} 字'
    )
)
def setup_long_text_entry(context, bot_id, field, n0, n1):
    _add_entry(
        context,
        _entry(bot_id, {field: {"before": "x" * n0, "after": "y" * n1}}),
    )


@given(parsers.parse('稽核紀錄有 {count:d} 筆 "{bot_id}" 的 update'))
def setup_many_entries(context, count, bot_id):
    for i in range(count):
        _add_entry(
            context,
            _entry(bot_id, {"name": {"before": f"n{i}", "after": f"n{i + 1}"}}, seq=i),
        )


@given(
    parsers.re(
        r'稽核紀錄有一筆 worker "(?P<worker_id>[^"]+)"'
        r'（屬 "(?P<bot_id>[^"]+)"）的 update，'
        r'將 "(?P<field>[^"]+)" 從 "(?P<before>[^"]*)" 改為 "(?P<after>[^"]*)"$'
    )
)
def setup_worker_scalar_entry(context, bot_id, worker_id, field, before, after):
    _add_entry(
        context,
        _worker_entry(bot_id, worker_id, {field: {"before": before, "after": after}}),
    )


@given(
    parsers.re(
        r'稽核紀錄有一筆 worker "(?P<worker_id>[^"]+)"'
        r'（屬 "(?P<bot_id>[^"]+)"）的 update，'
        r'將 "(?P<field>[^"]+)" 從 (?P<n0>\d+) 字改為 (?P<n1>\d+) 字$'
    )
)
def setup_worker_long_text_entry(context, bot_id, worker_id, field, n0, n1):
    _add_entry(
        context,
        _worker_entry(
            bot_id, worker_id,
            {field: {"before": "x" * int(n0), "after": "y" * int(n1)}},
        ),
    )


@given(
    parsers.re(
        r'稽核紀錄有一筆 worker "(?P<worker_id>[^"]+)"'
        r'（屬 "(?P<bot_id>[^"]+)"）的 delete，'
        r'快照名稱為 "(?P<name>[^"]+)"$'
    )
)
def setup_worker_delete_entry(context, bot_id, worker_id, name):
    _add_entry(
        context,
        _worker_entry(
            bot_id, worker_id,
            {"name": {"before": name, "after": None}},
            action="delete",
        ),
    )


@given(parsers.parse('worker "{worker_id}" 目前名稱為 "{name}"'))
def setup_worker_name(context, worker_id, name):
    worker = WorkerConfig(id=worker_id, bot_id="bot-001", name=name)
    context["worker_repo"].find_by_bot_id = AsyncMock(return_value=[worker])


@given("worker 用例已注入稽核紀錄器與 bot repository")
def setup_worker_use_cases(context):
    """Issue #77：worker 寫入稽核帶 tenant_id（自 bot 解析）與 parent=bot。"""
    audit_repo = AsyncMock()
    audit_repo.append = AsyncMock()
    audit = AuditRecorder(repository=audit_repo)
    context["audit_append"] = audit_repo.append

    store: dict = {}
    repo = AsyncMock(spec=WorkerConfigRepository)

    async def _save(w):
        store[w.id] = w

    async def _find(wid):
        return store.get(wid)

    async def _delete(wid):
        store.pop(wid, None)

    repo.save = AsyncMock(side_effect=_save)
    repo.find_by_id = AsyncMock(side_effect=_find)
    repo.delete = AsyncMock(side_effect=_delete)
    kwargs = {"repo": repo, "audit": audit, "bot_repository": context["bot_repo"]}
    context["create_uc"] = CreateWorkerUseCase(**kwargs)
    context["update_uc"] = UpdateWorkerUseCase(**kwargs)
    context["delete_uc"] = DeleteWorkerUseCase(**kwargs)


# ── When ──


def _worker_audit_entries(context) -> list[AuditEntry]:
    return [
        c.args[0] for c in context["audit_append"].await_args_list
        if c.args[0].entity_type == "worker"
    ]


@when(parsers.parse('使用者 "{actor}" 在 "{bot_id}" 建立 worker "{name}"'))
def create_worker(context, actor, bot_id, name):
    context["worker"] = _run(context["create_uc"].execute(CreateWorkerCommand(
        bot_id=bot_id, name=name, actor_user_id=actor,
    )))


@when(
    parsers.parse(
        '使用者 "{actor}" 在 "{bot_id}" 建立 worker "{name}" '
        '再改 prompt 為 "{prompt}" 再刪除'
    )
)
def worker_lifecycle(context, actor, bot_id, name, prompt):
    w = _run(context["create_uc"].execute(CreateWorkerCommand(
        bot_id=bot_id, name=name, worker_prompt="原", actor_user_id=actor,
    )))
    _run(context["update_uc"].execute(UpdateWorkerCommand(
        worker_id=w.id, bot_id=bot_id, worker_prompt=prompt, actor_user_id=actor,
    )))
    _run(context["delete_uc"].execute(w.id, actor_user_id=actor, bot_id=bot_id))



def _execute(context, bot_id, tenant_id, role, **kwargs):
    use_case = ListBotAuditLogsUseCase(
        bot_repository=context["bot_repo"],
        audit_log_repository=context["audit_repo"],
        user_repository=context["user_repo"],
        worker_repository=context["worker_repo"],
    )
    try:
        context["result"] = _run(
            use_case.execute(bot_id, tenant_id=tenant_id, role=role, **kwargs)
        )
        context["error"] = None
    except EntityNotFoundError as e:
        context["result"] = None
        context["error"] = e


@when(
    parsers.re(
        r'租戶 "(?P<tenant_id>[^"]+)" 的 "(?P<role>[^"]+)" '
        r'查詢 "(?P<bot_id>[^"]+)" 的變更紀錄'
    )
)
def query_default(context, tenant_id, role, bot_id):
    _execute(context, bot_id, tenant_id, role)


@when(
    parsers.re(
        r'租戶 "(?P<tenant_id>[^"]+)" 的 "(?P<role>[^"]+)" 以 limit (?P<limit>\d+) '
        r'查詢 "(?P<bot_id>[^"]+)" 的變更紀錄'
    )
)
def query_with_limit(context, tenant_id, role, limit, bot_id):
    _execute(context, bot_id, tenant_id, role, limit=int(limit))


@when(
    parsers.re(
        r'租戶 "(?P<tenant_id>[^"]+)" 的 "(?P<role>[^"]+)" '
        r'以 cursor "(?P<cursor>[^"]+)" '
        r'查詢 "(?P<bot_id>[^"]+)" 的變更紀錄'
    )
)
def query_with_cursor(context, tenant_id, role, cursor, bot_id):
    _execute(context, bot_id, tenant_id, role, cursor=cursor)


# ── Then ──


def _page(context) -> BotAuditLogPage:
    assert context["error"] is None, f"Unexpected error: {context['error']}"
    return context["result"]


def _change(context, index: int, field: str):
    entry = _page(context).items[index - 1]
    matches = [c for c in entry.changes if c.field == field]
    fields = [c.field for c in entry.changes]
    assert matches, f"field {field!r} not in changes: {fields}"
    return matches[0]


@then(parsers.parse("應回傳 {count:d} 筆紀錄"))
def check_count(context, count):
    assert len(_page(context).items) == count


@then(parsers.parse('第 {index:d} 筆紀錄的操作者 email 應為 "{email}"'))
def check_actor_email(context, index, email):
    assert _page(context).items[index - 1].actor_email == email


@then(parsers.parse("第 {index:d} 筆紀錄的操作者 email 應為空"))
def check_actor_email_empty(context, index):
    assert _page(context).items[index - 1].actor_email is None


@then(
    parsers.parse(
        '第 {index:d} 筆紀錄應含欄位 "{field}" 由 "{before}" 變為 "{after}"'
    )
)
def check_change(context, index, field, before, after):
    change = _change(context, index, field)
    assert str(change.before) == before
    assert str(change.after) == after


@then(parsers.parse('第 {index:d} 筆紀錄不應含欄位 "{field}"'))
def check_no_change(context, index, field):
    entry = _page(context).items[index - 1]
    assert field not in [c.field for c in entry.changes]


@then(
    parsers.parse(
        '第 {index:d} 筆紀錄的欄位 "{field}" 應只回 before_len {n0:d}、after_len {n1:d}'
    )
)
def check_long_text_lengths(context, index, field, n0, n1):
    change = _change(context, index, field)
    assert change.before_len == n0
    assert change.after_len == n1
    assert change.changed is True


@then(parsers.parse('第 {index:d} 筆紀錄的欄位 "{field}" 不應含全文'))
def check_long_text_omitted(context, index, field):
    change = _change(context, index, field)
    assert change.before is None
    assert change.after is None


@then(
    parsers.parse(
        '查詢條件應為 entity_type "{entity_type}" 且 entity_id "{entity_id}"，'
        '並聯集 parent "{parent_type}" "{parent_id}"'
    )
)
def check_query_filter(context, entity_type, entity_id, parent_type, parent_id):
    """Issue #77：bot 列與其 worker 列以單一 keyset 查詢聯集取得。"""
    kwargs = context["audit_repo"].find_by_entity_or_parent.call_args.kwargs
    assert kwargs["entity_type"] == entity_type
    assert kwargs["entity_id"] == entity_id
    assert kwargs["parent_entity_type"] == parent_type
    assert kwargs["parent_entity_id"] == parent_id


def _entry_of_type(context, entity_type: str):
    matches = [e for e in _page(context).items if e.entity_type == entity_type]
    assert matches, f"no entry with entity_type={entity_type!r}"
    return matches[0]


@then(
    parsers.parse('其中 entity_type "{entity_type}" 的紀錄 entity_name 應為 "{name}"')
)
def check_entity_name(context, entity_type, name):
    assert _entry_of_type(context, entity_type).entity_name == name


@then(parsers.parse('其中 entity_type "{entity_type}" 的紀錄 entity_name 應為空'))
def check_entity_name_empty(context, entity_type):
    assert _entry_of_type(context, entity_type).entity_name is None


@then(
    parsers.parse(
        '其中 entity_type "{entity_type}" 的紀錄應含欄位 "{field}" '
        '由 "{before}" 變為 "{after}"'
    )
)
def check_typed_change(context, entity_type, field, before, after):
    entry = _entry_of_type(context, entity_type)
    matches = [c for c in entry.changes if c.field == field]
    assert matches, [c.field for c in entry.changes]
    assert str(matches[0].before) == before
    assert str(matches[0].after) == after


@then(parsers.parse('worker 稽核列的 tenant_id 應為 "{tenant_id}"'))
def check_worker_audit_tenant(context, tenant_id):
    entries = _worker_audit_entries(context)
    assert entries, "no worker audit entry written"
    assert entries[-1].tenant_id == tenant_id


@then(parsers.parse('worker 稽核列的 parent 應為 "{ptype}" "{pid}"'))
def check_worker_audit_parent(context, ptype, pid):
    entry = _worker_audit_entries(context)[-1]
    assert (entry.parent_entity_type, entry.parent_entity_id) == (ptype, pid)


@then(parsers.parse('worker 稽核列的 action 應為 "{action}"'))
def check_worker_audit_action(context, action):
    assert _worker_audit_entries(context)[-1].action == action


@then(
    parsers.parse(
        '每筆 worker 稽核列的 tenant_id 都應為 "{tenant_id}" '
        '且 parent 為 "{ptype}" "{pid}"'
    )
)
def check_all_worker_audit_links(context, tenant_id, ptype, pid):
    entries = _worker_audit_entries(context)
    assert entries
    for e in entries:
        assert e.tenant_id == tenant_id, e
        assert (e.parent_entity_type, e.parent_entity_id) == (ptype, pid), e


@then(parsers.parse("worker 稽核列的 action 依序為 {actions}"))
def check_worker_audit_actions(context, actions):
    expected = [a.strip().strip('"') for a in actions.split(",")]
    assert [e.action for e in _worker_audit_entries(context)] == expected


@then("應拋出 EntityNotFoundError")
def check_not_found(context):
    assert isinstance(context["error"], EntityNotFoundError)


@then("不應查詢稽核紀錄")
def check_audit_not_queried(context):
    context["audit_repo"].find_by_entity.assert_not_called()


@then(parsers.parse("next_cursor 應指向第 {index:d} 筆紀錄"))
def check_next_cursor(context, index):
    page = _page(context)
    expected = encode_audit_cursor(context["entries"][index - 1])
    assert page.next_cursor == expected
    assert page.items[index - 1].id == context["entries"][index - 1].id


@then("next_cursor 應為空")
def check_next_cursor_empty(context):
    assert _page(context).next_cursor is None


@then(parsers.parse('repository 應以 cursor "{cursor}" 被呼叫'))
def check_cursor_forwarded(context, cursor):
    union_kwargs = context["audit_repo"].find_by_entity_or_parent.call_args.kwargs
    guard_kwargs = context["audit_repo"].find_by_entity.call_args.kwargs
    assert union_kwargs["cursor"] == cursor
    assert guard_kwargs["cursor"] == cursor
