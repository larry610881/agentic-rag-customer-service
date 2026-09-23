"""GetUserUseCase 與其跨租戶邊界（Issue #101 B8 regression）。

GetUserUseCase 以純 user_id 查詢、不帶 tenant 條件——這是刻意的：它只服務
system_admin 的 `/admin/users/{id}`（平台管理需跨租戶檢視）。因此「別租戶的使用者
不得被回傳」這條保證落在入口：非 system_admin（含他租戶的 tenant_admin）一律 403，
碰不到這個 use case。這裡同時守 use case 語意與入口的角色閘門，任何一邊被放寬
（例如新增一個租戶可達的路由卻沿用此 use case）都會紅。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.application.auth.get_user_use_case import GetUserUseCase
from src.domain.auth.entity import User
from src.domain.auth.repository import UserRepository
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api import admin_router
from src.interfaces.api.deps import CurrentTenant, require_role


def _repo(user: User | None) -> AsyncMock:
    repo = AsyncMock(spec=UserRepository)
    repo.find_by_id.return_value = user
    return repo


def test_returns_user_by_id():
    user = User(tenant_id="tenant-a")
    repo = _repo(user)
    assert asyncio.run(GetUserUseCase(repo).execute("u-1")) is user
    repo.find_by_id.assert_awaited_once_with("u-1")


def test_missing_user_raises_not_found():
    with pytest.raises(EntityNotFoundError):
        asyncio.run(GetUserUseCase(_repo(None)).execute("ghost"))


def _get_user_route_role_gates() -> list[tuple[str, ...]]:
    """找出掛 GetUserUseCase 的路由，回傳它們 require_role 閘門允許的角色。"""
    gates = []
    for route in admin_router.router.routes:
        if getattr(route, "endpoint", None) is not admin_router.get_user:
            continue
        for dep in route.dependant.dependencies:
            call = dep.call
            if getattr(call, "__qualname__", "") == "require_role.<locals>._check":
                gates.append(call.__closure__[0].cell_contents)
    return gates


def test_get_user_endpoint_only_reachable_by_system_admin():
    assert _get_user_route_role_gates() == [("system_admin",)]


def test_other_tenant_admin_is_rejected_before_lookup():
    """tenant-b 的 tenant_admin 想讀 tenant-a 的使用者 → 403，use case 不被呼叫。"""
    check = require_role("system_admin")
    caller = CurrentTenant(tenant_id="tenant-b", user_id="u-b", role="tenant_admin")
    with pytest.raises(HTTPException) as ei:
        asyncio.run(check(tenant=caller))
    assert ei.value.status_code == 403
