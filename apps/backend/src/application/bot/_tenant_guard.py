"""Bot 資源歸屬檢查（C8/C9）。

bot_router 的 Get/Update/Delete use case 原本以純 bot_id 查詢、不比對 tenant，
造成跨租戶 IDOR。此 helper 統一歸屬判定：非擁有者且非 system_admin → 視同不存在
（raise EntityNotFoundError → 404，不洩漏資源存在性）。system_admin 保留跨租戶
存取（admin 檢視需要）。
"""

from __future__ import annotations

from src.domain.bot.entity import Bot
from src.domain.shared.exceptions import EntityNotFoundError

SYSTEM_ADMIN_ROLE = "system_admin"


def ensure_bot_tenant(bot: Bot, tenant_id: str, role: str | None) -> None:
    if role == SYSTEM_ADMIN_ROLE:
        return
    if bot.tenant_id != tenant_id:
        raise EntityNotFoundError("Bot", bot.id.value)
