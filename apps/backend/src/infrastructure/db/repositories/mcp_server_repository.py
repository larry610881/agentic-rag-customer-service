"""MCP Server Registration Repository 實作"""

from sqlalchemy import cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.platform.entity import McpServerRegistration
from src.domain.platform.repository import McpServerRegistrationRepository
from src.domain.platform.value_objects import McpRegistryId, McpRegistryToolMeta
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.mcp_server_model import McpServerModel


class SQLAlchemyMcpServerRepository(McpServerRegistrationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: McpServerModel) -> McpServerRegistration:
        return McpServerRegistration(
            id=McpRegistryId(value=model.id),
            name=model.name,
            description=model.description or "",
            transport=model.transport or "http",
            url=model.url or "",
            command=model.command or "",
            args=list(model.args or []),
            required_env=list(model.required_env or []),
            available_tools=[
                McpRegistryToolMeta(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                )
                for t in (model.available_tools or [])
            ],
            version=model.version or "",
            scope=model.scope or "global",
            tenant_ids=list(model.tenant_ids or []),
            is_enabled=model.is_enabled,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, server: McpServerRegistration) -> None:
        async with atomic(self._session):
            tools_data = [
                {"name": t.name, "description": t.description}
                for t in server.available_tools
            ]
            existing = await self._session.get(
                McpServerModel, server.id.value
            )
            if existing:
                existing.name = server.name
                existing.description = server.description
                existing.transport = server.transport
                existing.url = server.url
                existing.command = server.command
                existing.args = server.args
                existing.required_env = server.required_env
                existing.available_tools = tools_data
                existing.version = server.version
                existing.scope = server.scope
                existing.tenant_ids = server.tenant_ids
                existing.is_enabled = server.is_enabled
                existing.updated_at = server.updated_at
            else:
                model = McpServerModel(
                    id=server.id.value,
                    name=server.name,
                    description=server.description,
                    transport=server.transport,
                    url=server.url,
                    command=server.command,
                    args=server.args,
                    required_env=server.required_env,
                    available_tools=tools_data,
                    version=server.version,
                    scope=server.scope,
                    tenant_ids=server.tenant_ids,
                    is_enabled=server.is_enabled,
                    created_at=server.created_at,
                    updated_at=server.updated_at,
                )
                self._session.add(model)

    async def find_by_id(self, id: str) -> McpServerRegistration | None:
        stmt = select(McpServerModel).where(McpServerModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_all(self) -> list[McpServerRegistration]:
        stmt = select(McpServerModel).order_by(McpServerModel.created_at)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_accessible(
        self, tenant_id: str
    ) -> list[McpServerRegistration]:
        stmt = (
            select(McpServerModel)
            .where(
                McpServerModel.is_enabled.is_(True),
                or_(
                    McpServerModel.scope == "global",
                    cast(McpServerModel.tenant_ids, JSONB).contains(
                        [tenant_id]
                    ),
                ),
            )
            .order_by(McpServerModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_url(self, url: str) -> McpServerRegistration | None:
        stmt = select(McpServerModel).where(McpServerModel.url == url)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def delete(self, id: str) -> None:
        async with atomic(self._session):
            existing = await self._session.get(McpServerModel, id)
            if existing:
                await self._session.delete(existing)
