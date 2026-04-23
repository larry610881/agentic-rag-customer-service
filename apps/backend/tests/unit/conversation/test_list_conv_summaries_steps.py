"""BDD: unit/conversation/list_conv_summaries.feature

S-KB-Followup.1: UseCase 加了 bot_repo 做 IDOR 防護，step_def 同步更新。
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.conversation.list_conv_summaries_use_case import (
    ListConvSummariesQuery,
    ListConvSummariesUseCase,
)
from src.domain.shared.exceptions import EntityNotFoundError
from tests.unit.knowledge.kb_studio_fixtures import run

scenarios("unit/conversation/list_conv_summaries.feature")


@pytest.fixture
def ctx():
    return {}


def _build_conv_repo(summaries_by_tenant):
    """summaries_by_tenant: {tenant_id: [{"bot_id":..., ...}, ...]}"""
    repo = AsyncMock()

    async def find(
        tenant_id, bot_id=None, page=1, page_size=50, **kw
    ):
        items = summaries_by_tenant.get(tenant_id, [])
        if bot_id:
            items = [s for s in items if s["bot_id"] == bot_id]
        return items

    repo.find_conv_summaries = find
    return repo


def _build_bot_repo(ctx):
    """模擬 BotRepository.exists_for_tenant：依 ctx['bot_owner'] 驗證。
    預設：任何 bot_id 都視為屬該 tenant（happy path）。
    若 ctx['bot_owner'] 存在：只有 (owner_tenant, owner_bot) 對才回 True。
    """
    repo = AsyncMock()
    bot_owner = ctx.get("bot_owner")

    async def exists_for_tenant(bot_id: str, tenant_id: str) -> bool:
        if bot_owner is None:
            return True
        owner_tenant, owner_bot = bot_owner
        if owner_bot == bot_id:
            return owner_tenant == tenant_id
        return True

    repo.exists_for_tenant = exists_for_tenant
    return repo


@given(
    parsers.parse(
        '租戶 "{tenant_id}" 有 {n:d} 筆 conv_summaries（{a:d} 筆 bot="{bot_a}"、{b:d} 筆 bot="{bot_b}"）'
    )
)
def seed_cross_bot(ctx, tenant_id, n, a, bot_a, b, bot_b):
    summaries = {
        tenant_id: (
            [{"bot_id": bot_a, "tenant_id": tenant_id} for _ in range(a)]
            + [{"bot_id": bot_b, "tenant_id": tenant_id} for _ in range(b)]
        )
    }
    ctx["by_tenant"] = summaries


@given(parsers.parse('租戶 "{tenant_id}" 有 {n:d} 筆 conv_summaries'))
def seed_simple(ctx, tenant_id, n):
    ctx.setdefault("by_tenant", {})
    ctx["by_tenant"][tenant_id] = [
        {"bot_id": "bot-X", "tenant_id": tenant_id} for _ in range(n)
    ]


@given(parsers.parse('租戶 "{tenant_id}" 有 conv_summaries 跨 bot-A({a:d}) + bot-B({b:d})'))
def seed_cross_bot_short(ctx, tenant_id, a, b):
    ctx["by_tenant"] = {
        tenant_id: (
            [{"bot_id": "bot-A", "tenant_id": tenant_id} for _ in range(a)]
            + [{"bot_id": "bot-B", "tenant_id": tenant_id} for _ in range(b)]
        )
    }


@given(parsers.parse('租戶 "{tenant_id}" 擁有 bot "{bot_id}"'))
def seed_bot_owner(ctx, tenant_id, bot_id):
    ctx["bot_owner"] = (tenant_id, bot_id)
    ctx.setdefault("by_tenant", {})
    ctx["by_tenant"].setdefault(tenant_id, [])


def _run_list(ctx, *, tenant_id=None, bot_id=None, role="system_admin"):
    conv_repo = _build_conv_repo(ctx.get("by_tenant", {}))
    bot_repo = _build_bot_repo(ctx)
    uc = ListConvSummariesUseCase(conv_repo, bot_repo)
    try:
        ctx["result"] = run(
            uc.execute(
                ListConvSummariesQuery(
                    role=role, tenant_id=tenant_id, bot_id=bot_id
                )
            )
        )
        ctx["error"] = None
    except Exception as e:
        ctx["error"] = e
        ctx["result"] = None


@when(
    parsers.parse(
        '我以 tenant "{tenant}" 的 tenant_admin 身分呼叫 list_conv_summaries(tenant_id="{tenant_id}")'
    )
)
def when_tenant(ctx, tenant, tenant_id):
    _run_list(ctx, tenant_id=tenant_id, role="tenant_admin")


@when(
    parsers.parse(
        '我呼叫 list_conv_summaries(tenant_id="{tenant_id}", bot_id="{bot_id}")'
    )
)
def when_bot_filter(ctx, tenant_id, bot_id):
    _run_list(ctx, tenant_id=tenant_id, bot_id=bot_id, role="tenant_admin")


@when(
    parsers.parse(
        '我以 tenant "{tenant}" 身分呼叫 list_conv_summaries(tenant_id="{tenant_id}", bot_id="{bot_id}")'
    )
)
def when_cross_tenant_bot(ctx, tenant, tenant_id, bot_id):
    # 讓 use case 內部的 exists_for_tenant 擋（IDOR 修補後的行為）
    _run_list(ctx, tenant_id=tenant_id, bot_id=bot_id, role="tenant_admin")


@when("我以 platform_admin 身分呼叫 list_conv_summaries()（無 tenant_id）")
def when_platform_no_tenant(ctx):
    _run_list(ctx, tenant_id=None, bot_id=None, role="system_admin")


@then(parsers.parse("回傳應含 {n:d} 筆"))
def then_count(ctx, n):
    assert ctx["error"] is None
    assert len(ctx["result"]) == n


@then(parsers.parse('所有筆數的 tenant_id 應為 "{tenant_id}"'))
def then_all_tenant(ctx, tenant_id):
    assert all(s["tenant_id"] == tenant_id for s in ctx["result"])


@then(parsers.parse('所有筆數的 bot_id 應為 "{bot_id}"'))
def then_all_bot(ctx, bot_id):
    assert all(s["bot_id"] == bot_id for s in ctx["result"])


@then("應拋出 EntityNotFoundError（404 防枚舉）")
def then_nf(ctx):
    assert isinstance(ctx["error"], EntityNotFoundError)


@then(parsers.parse('應拋出 ValueError 訊息含 "{needle}"'))
def then_ve(ctx, needle):
    assert isinstance(ctx["error"], ValueError)
    assert needle in str(ctx["error"])
