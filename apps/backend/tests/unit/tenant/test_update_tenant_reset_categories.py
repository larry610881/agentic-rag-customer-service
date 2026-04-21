"""UpdateTenantUseCase — included_categories 支援三種語意（Bug 2 修復）

Sentinel pattern：
- command.included_categories is _UNSET  → 不改（保持既有值）
- command.included_categories is None    → 顯式重置為 NULL
- command.included_categories == [...]   → 明確寫入

Plan: .claude/plans/b-bug-delightful-starlight.md
Issue: #35
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from src.application.tenant.update_tenant_use_case import (
    UpdateTenantCommand,
    UpdateTenantUseCase,
)
from src.domain.tenant.entity import Tenant
from src.domain.tenant.value_objects import TenantId


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mk_tenant(included: list[str] | None) -> Tenant:
    return Tenant(
        id=TenantId(value="t-1"),
        name="T",
        plan="starter",
        included_categories=included,
    )


def _mk_use_case(tenant: Tenant) -> tuple[UpdateTenantUseCase, AsyncMock]:
    tenant_repo = AsyncMock()
    tenant_repo.find_by_id = AsyncMock(return_value=tenant)
    tenant_repo.save = AsyncMock()
    uc = UpdateTenantUseCase(
        tenant_repository=tenant_repo,
        plan_repository=None,
    )
    return uc, tenant_repo


def test_explicit_null_resets_included_categories_to_none():
    """admin 顯式送 null → included_categories 變 None（全計入）"""
    tenant = _mk_tenant(included=["rag", "chat_web"])
    uc, tenant_repo = _mk_use_case(tenant)

    command = UpdateTenantCommand(
        tenant_id="t-1",
        included_categories=None,  # explicit null
    )
    result = _run(uc.execute(command))

    assert result.included_categories is None
    tenant_repo.save.assert_awaited_once()


def test_unset_sentinel_preserves_existing_value():
    """command 不帶 included_categories（default = _UNSET）→ 保持既有值"""
    tenant = _mk_tenant(included=["rag"])
    uc, tenant_repo = _mk_use_case(tenant)

    # 不傳 included_categories，使用 sentinel default
    command = UpdateTenantCommand(
        tenant_id="t-1",
        monthly_token_limit=999,
    )
    result = _run(uc.execute(command))

    assert result.included_categories == ["rag"]  # 維持原值
    assert result.monthly_token_limit == 999      # 其他欄位有更新
    tenant_repo.save.assert_awaited_once()


def test_explicit_empty_list_sets_empty():
    """admin 顯式送空陣列 → 全不計入（POC 免計費）"""
    tenant = _mk_tenant(included=None)
    uc, _ = _mk_use_case(tenant)

    command = UpdateTenantCommand(
        tenant_id="t-1",
        included_categories=[],
    )
    result = _run(uc.execute(command))

    assert result.included_categories == []


def test_explicit_list_overwrites_existing():
    """admin 送新 list → 覆蓋既有值"""
    tenant = _mk_tenant(included=["rag"])
    uc, _ = _mk_use_case(tenant)

    command = UpdateTenantCommand(
        tenant_id="t-1",
        included_categories=["chat_web", "embedding"],
    )
    result = _run(uc.execute(command))

    assert result.included_categories == ["chat_web", "embedding"]


def test_unset_preserves_none_value_too():
    """既有值為 None 時，未帶 included_categories 仍保持 None（不會意外變 []）"""
    tenant = _mk_tenant(included=None)
    uc, _ = _mk_use_case(tenant)

    command = UpdateTenantCommand(tenant_id="t-1", monthly_token_limit=500)
    result = _run(uc.execute(command))

    assert result.included_categories is None


def test_other_fields_also_use_sentinel_semantics():
    """驗證其他 optional 欄位（plan / limit / default_*_model）一樣支援 _UNSET。"""
    tenant = _mk_tenant(included=["rag"])
    tenant.monthly_token_limit = 123
    tenant.default_ocr_model = "existing-ocr"
    uc, _ = _mk_use_case(tenant)

    # 只改 included_categories，其他欄位都不傳
    command = UpdateTenantCommand(
        tenant_id="t-1",
        included_categories=None,  # reset
    )
    result = _run(uc.execute(command))

    # 未傳的欄位保留
    assert result.monthly_token_limit == 123
    assert result.default_ocr_model == "existing-ocr"
    assert result.included_categories is None  # 已重置
