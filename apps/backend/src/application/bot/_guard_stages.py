"""Bot 層防護階段覆寫驗證（Issue #75）— create / update use case 共用。

規則：None = 繼承租戶有效值；list 必須是租戶有效集合的超集（只能加不能減）；
租戶被平台鎖定時不得自設。provider 未注入（舊接線 / 測試）時只驗階段名稱。
"""

from __future__ import annotations

from typing import Any

from src.domain.security.guard_stages import (
    normalize_stage_list,
    validate_bot_guard_stages,
)


async def validate_bot_guard_stages_for_tenant(
    stages: Any, tenant_id: str, guard_provider: Any | None
) -> list[str] | None:
    if stages is None:
        return None
    if guard_provider is None:
        return normalize_stage_list(list(stages))
    effective = await guard_provider.effective_for(tenant_id)
    return validate_bot_guard_stages(list(stages), effective)
