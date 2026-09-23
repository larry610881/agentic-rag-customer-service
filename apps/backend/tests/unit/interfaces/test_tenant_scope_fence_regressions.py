"""Regression：tenant scope fence（Issue #101）抓到的缺擁有權檢查端點。

- GET /api/v1/bots/{bot_id}/config-timeline
  以純 bot_id 查 trace 的設定指紋時間軸，任一租戶可列出他租戶 bot 的 config_hash；
  再拿 hash 打 GET /config-snapshots/{hash}（內容定址、無租戶欄）即可讀到對方 bot
  的完整有效設定——含覆蓋後的 system prompt。
- GET /api/v1/tenants/{tenant_id}
  任一登入者可讀任一租戶的名稱、方案、token 上限與預設模型設定。

跨租戶一律 404（防枚舉），且不得讀資料；system_admin 維持可跨租戶。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api import config_snapshot_router, tenant_router
from src.interfaces.api.deps import CurrentTenant
from src.interfaces.api.errors import ApiError

ATTACKER = CurrentTenant(tenant_id="tenant-a", user_id="u-a", role="tenant_admin")
ADMIN = CurrentTenant(tenant_id="sys", user_id="root", role="system_admin")


def _get_bot_owned_by_b() -> AsyncMock:
    """GetBotUseCase：bot-b 屬於 tenant-b，非本租戶一律 EntityNotFoundError。"""

    async def execute(bot_id, tenant_id=None, role=None):
        if role != "system_admin" and tenant_id != "tenant-b":
            raise EntityNotFoundError("Bot", bot_id)
        return object()

    uc = AsyncMock()
    uc.execute.side_effect = execute
    return uc


def test_跨租戶不能讀_bot_設定時間軸():
    timeline = AsyncMock()
    timeline.execute.return_value = [{"hash": "h" * 64}]
    with pytest.raises(ApiError) as exc:
        asyncio.run(
            config_snapshot_router.get_bot_config_timeline(
                bot_id="bot-b",
                limit=50,
                tenant=ATTACKER,
                use_case=timeline,
                get_bot=_get_bot_owned_by_b(),
            )
        )
    assert exc.value.status_code == 404
    timeline.execute.assert_not_awaited()


def test_system_admin_可讀任一_bot_設定時間軸():
    timeline = AsyncMock()
    timeline.execute.return_value = []
    result = asyncio.run(
        config_snapshot_router.get_bot_config_timeline(
            bot_id="bot-b",
            limit=50,
            tenant=ADMIN,
            use_case=timeline,
            get_bot=_get_bot_owned_by_b(),
        )
    )
    assert result == {"bot_id": "bot-b", "items": []}
    timeline.execute.assert_awaited_once_with("bot-b", limit=50)


def test_跨租戶不能讀租戶資料():
    use_case = AsyncMock()
    with pytest.raises(ApiError) as exc:
        asyncio.run(
            tenant_router.get_tenant(
                tenant_id="tenant-b", caller=ATTACKER, use_case=use_case
            )
        )
    assert exc.value.status_code == 404
    use_case.execute.assert_not_awaited()


@pytest.mark.parametrize(
    ("caller", "tenant_id"),
    [(ATTACKER, "tenant-a"), (ADMIN, "tenant-b")],
)
def test_本租戶與_system_admin_仍可讀租戶資料(caller, tenant_id):
    use_case = AsyncMock()
    use_case.execute.side_effect = EntityNotFoundError("Tenant", tenant_id)
    with pytest.raises(ApiError):
        asyncio.run(
            tenant_router.get_tenant(
                tenant_id=tenant_id, caller=caller, use_case=use_case
            )
        )
    use_case.execute.assert_awaited_once_with(tenant_id)
