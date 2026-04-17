"""Update built-in tool scope + tenant whitelist (system_admin only)."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.agent.built_in_tool import BuiltInTool, BuiltInToolRepository

_ALLOWED_SCOPES = {"global", "tenant"}


@dataclass
class UpdateBuiltInToolScopeUseCase:
    repository: BuiltInToolRepository

    async def execute(
        self, *, name: str, scope: str, tenant_ids: list[str]
    ) -> BuiltInTool:
        if scope not in _ALLOWED_SCOPES:
            raise ValueError(f"Invalid scope: {scope}")
        if scope == "tenant" and not tenant_ids:
            raise ValueError("tenant scope requires non-empty tenant_ids")

        tool = await self.repository.find_by_name(name)
        if tool is None:
            raise LookupError(f"Built-in tool not found: {name}")

        tool.scope = scope
        tool.tenant_ids = list(tenant_ids) if scope == "tenant" else []
        await self.repository.upsert(tool)
        return tool
