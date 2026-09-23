"""租戶隔離 helper 全分支（Issue #101 B8，下限 100%）。

- knowledge/_admin_kb_check：同租戶 / 跨租戶 404 / system_admin bypass / KB 不存在
- bot/_tenant_guard：擁有者 / 跨租戶 404 / system_admin
- eval_dataset/_tenant_guard：讀（擁有者、平台集、跨租戶 404、admin、未帶 tenant）
  與寫（平台集非 admin 403、跨租戶 404、擁有者、admin）

跨租戶一律回「不存在」（404）而非 403，避免洩漏資源存在性。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.application.bot._tenant_guard import ensure_bot_tenant
from src.application.eval_dataset._tenant_guard import (
    can_read_dataset,
    ensure_dataset_read,
    ensure_dataset_write,
)
from src.application.knowledge._admin_kb_check import (
    ensure_kb_accessible,
    is_system_admin,
    tenant_match_or_admin,
)
from src.domain.bot.entity import Bot
from src.domain.eval_dataset.entity import EvalDataset
from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.repository import KnowledgeBaseRepository
from src.domain.shared.constants import SYSTEM_TENANT_ID
from src.domain.shared.exceptions import AuthorizationError, EntityNotFoundError

_A = "tenant-a"
_B = "tenant-b"


def _kb_repo(kb: KnowledgeBase | None) -> AsyncMock:
    repo = AsyncMock(spec=KnowledgeBaseRepository)
    repo.find_by_id.return_value = kb
    return repo


# ---------------------------------------------------------------- knowledge


def test_is_system_admin():
    assert is_system_admin(SYSTEM_TENANT_ID) is True
    assert is_system_admin(_A) is False
    assert is_system_admin("") is False


@pytest.mark.parametrize(
    ("entity", "requester", "expected"),
    [
        (_A, _A, True),
        (_A, _B, False),
        (_A, SYSTEM_TENANT_ID, True),
        ("", _B, False),
    ],
)
def test_tenant_match_or_admin(entity, requester, expected):
    assert tenant_match_or_admin(entity, requester) is expected


def test_ensure_kb_same_tenant_returns_requester_tenant():
    kb = KnowledgeBase(tenant_id=_A)
    repo = _kb_repo(kb)
    got, eff = asyncio.run(ensure_kb_accessible(repo, "kb-1", _A))
    assert got is kb and eff == _A
    repo.find_by_id.assert_awaited_once_with("kb-1")


def test_ensure_kb_system_admin_gets_real_owner_tenant():
    kb = KnowledgeBase(tenant_id=_B)
    got, eff = asyncio.run(ensure_kb_accessible(_kb_repo(kb), "kb-1", SYSTEM_TENANT_ID))
    # effective tenant 必須是真實擁有者（Milvus filter 用），不是 SYSTEM_TENANT_ID
    assert got is kb and eff == _B


def test_ensure_kb_cross_tenant_is_not_found():
    repo = _kb_repo(KnowledgeBase(tenant_id=_B))
    with pytest.raises(EntityNotFoundError):
        asyncio.run(ensure_kb_accessible(repo, "k", _A))


def test_ensure_kb_missing_is_not_found_even_for_admin():
    for requester in (_A, SYSTEM_TENANT_ID):
        with pytest.raises(EntityNotFoundError):
            asyncio.run(ensure_kb_accessible(_kb_repo(None), "k", requester))


# ---------------------------------------------------------------- bot


def test_bot_owner_allowed():
    ensure_bot_tenant(Bot(tenant_id=_A), _A, "tenant_admin")


def test_bot_cross_tenant_not_found():
    with pytest.raises(EntityNotFoundError):
        ensure_bot_tenant(Bot(tenant_id=_B), _A, "tenant_admin")
    with pytest.raises(EntityNotFoundError):
        ensure_bot_tenant(Bot(tenant_id=_B), _A, None)


def test_bot_system_admin_bypass():
    ensure_bot_tenant(Bot(tenant_id=_B), _A, "system_admin")


# ---------------------------------------------------------------- eval dataset


def _ds(tenant: str = _B, platform: bool = False) -> EvalDataset:
    return EvalDataset(tenant_id=tenant, is_platform_base=platform)


@pytest.mark.parametrize(
    ("ds", "tenant", "role", "readable"),
    [
        (_ds(_A), _A, "user", True),                 # 擁有者
        (_ds(_B), _A, "user", False),                # 跨租戶
        (_ds(_B, platform=True), _A, "user", True),  # 平台集可跨租戶讀
        (_ds(_B), _A, "system_admin", True),         # admin
        (_ds(_B), None, None, True),                 # 未帶 tenant（舊行為）
    ],
)
def test_dataset_read(ds, tenant, role, readable):
    assert can_read_dataset(ds, tenant, role) is readable
    if readable:
        ensure_dataset_read(ds, tenant, role)
    else:
        with pytest.raises(EntityNotFoundError):
            ensure_dataset_read(ds, tenant, role)


def test_dataset_write_owner_and_admin_allowed():
    ensure_dataset_write(_ds(_A), _A, "user")
    ensure_dataset_write(_ds(_B), _A, "system_admin")
    ensure_dataset_write(_ds(_B, platform=True), _A, "system_admin")
    ensure_dataset_write(_ds(_B), None, None)


def test_dataset_write_platform_base_forbidden_for_tenant_even_owner():
    with pytest.raises(AuthorizationError):
        ensure_dataset_write(_ds(_B, platform=True), _A, "user")
    with pytest.raises(AuthorizationError):
        ensure_dataset_write(_ds(_A, platform=True), _A, "tenant_admin")


def test_dataset_write_cross_tenant_not_found():
    with pytest.raises(EntityNotFoundError):
        ensure_dataset_write(_ds(_B), _A, "tenant_admin")
