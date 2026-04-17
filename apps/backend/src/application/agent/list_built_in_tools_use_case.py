"""List built-in tools with tenant scope filtering."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.agent.built_in_tool import BuiltInTool, BuiltInToolRepository


@dataclass
class ListBuiltInToolsUseCase:
    repository: BuiltInToolRepository

    async def execute(
        self, *, tenant_id: str | None, is_admin: bool
    ) -> list[BuiltInTool]:
        """admin → 所有工具（含 scope 資訊）
        其他 → 依 tenant_id 過濾（global + 白名單）"""
        if is_admin:
            return await self.repository.find_all()
        if not tenant_id:
            return []
        return await self.repository.find_accessible(tenant_id)
