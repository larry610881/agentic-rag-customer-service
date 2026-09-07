"""BDD steps — 租戶端 Bot 變更紀錄可見性（Issue #71）"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.bot.list_bot_audit_logs_use_case import (
    BotAuditLogPage,
    ListBotAuditLogsUseCase,
)
from src.domain.audit.entity import AuditEntry, AuditLogRepository, encode_audit_cursor
from src.domain.auth.entity import User
from src.domain.auth.repository import UserRepository
from src.domain.auth.value_objects import Email, UserId
from src.domain.bot.entity import Bot
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
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
    user_repo = AsyncMock(spec=UserRepository)
    user_repo.find_by_id = AsyncMock(return_value=None)
    return {
        "bot_repo": bot_repo,
        "audit_repo": audit_repo,
        "user_repo": user_repo,
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


def _add_entry(context, entry: AuditEntry) -> None:
    context["entries"].append(entry)
    context["audit_repo"].find_by_entity = AsyncMock(
        side_effect=lambda **kw: list(context["entries"])[: kw["limit"]]
    )


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


# ── When ──


def _execute(context, bot_id, tenant_id, role, **kwargs):
    use_case = ListBotAuditLogsUseCase(
        bot_repository=context["bot_repo"],
        audit_log_repository=context["audit_repo"],
        user_repository=context["user_repo"],
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
        '查詢條件應為 entity_type "{entity_type}" 且 entity_id "{entity_id}"'
    )
)
def check_query_filter(context, entity_type, entity_id):
    kwargs = context["audit_repo"].find_by_entity.call_args.kwargs
    assert kwargs["entity_type"] == entity_type
    assert kwargs["entity_id"] == entity_id


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
    kwargs = context["audit_repo"].find_by_entity.call_args.kwargs
    assert kwargs["cursor"] == cursor
