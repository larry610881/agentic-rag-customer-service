from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.bot.entity import (
    Bot,
    BotLLMParams,
    BotMcpBinding,
    McpServerConfig,
    McpToolMeta,
)
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId, BotShortCode
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.bot_knowledge_base_model import (
    BotKnowledgeBaseModel,
)
from src.infrastructure.db.models.bot_model import BotModel


class SQLAlchemyBotRepository(BotRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(
        self, model: BotModel, kb_ids: list[str]
    ) -> Bot:
        return Bot(
            id=BotId(value=model.id),
            short_code=BotShortCode(value=model.short_code),
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description,
            is_active=model.is_active,
            system_prompt=model.system_prompt,
            knowledge_base_ids=kb_ids,
            llm_params=BotLLMParams(
                temperature=model.temperature,
                max_tokens=model.max_tokens,
                history_limit=model.history_limit,
                frequency_penalty=model.frequency_penalty,
                reasoning_effort=model.reasoning_effort,
                rag_top_k=model.rag_top_k,
                rag_score_threshold=model.rag_score_threshold,
            ),
            enabled_tools=(
                list(model.enabled_tools)
                if model.enabled_tools is not None
                else ["rag_query"]
            ),
            llm_provider=model.llm_provider or "",
            llm_model=model.llm_model or "",
            show_sources=model.show_sources,
            agent_mode=model.agent_mode or "router",
            mcp_servers=[
                McpServerConfig(
                    url=s.get("url", ""),
                    name=s.get("name", ""),
                    enabled_tools=s.get("enabled_tools", []),
                    tools=[
                        McpToolMeta(
                            name=t.get("name", ""),
                            description=t.get("description", ""),
                        )
                        for t in s.get("tools", [])
                    ],
                    version=s.get("version", ""),
                )
                for s in (model.mcp_servers or [])
            ],
            mcp_bindings=[
                BotMcpBinding(
                    registry_id=b.get("registry_id", ""),
                    enabled_tools=b.get("enabled_tools", []),
                    env_values=b.get("env_values", {}),
                )
                for b in (model.mcp_bindings or [])
            ],
            max_tool_calls=model.max_tool_calls,
            audit_mode=model.audit_mode or "minimal",
            eval_provider=model.eval_provider or "",
            eval_model=model.eval_model or "",
            eval_depth=model.eval_depth or "L1",
            base_prompt=model.base_prompt or "",
            router_prompt=model.router_prompt or "",
            react_prompt=model.react_prompt or "",
            widget_enabled=model.widget_enabled if model.widget_enabled is not None else False,
            widget_allowed_origins=list(model.widget_allowed_origins or []),
            widget_keep_history=model.widget_keep_history if model.widget_keep_history is not None else True,
            avatar_type=model.avatar_type or "none",
            avatar_model_url=model.avatar_model_url or "",
            widget_welcome_message=model.widget_welcome_message or "",
            widget_placeholder_text=model.widget_placeholder_text or "",
            widget_greeting_messages=list(model.widget_greeting_messages or []),
            widget_greeting_animation=model.widget_greeting_animation or "fade",
            line_channel_secret=model.line_channel_secret,
            line_channel_access_token=model.line_channel_access_token,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def _get_all_kb_ids(
        self, bot_ids: list[str]
    ) -> dict[str, list[str]]:
        if not bot_ids:
            return {}
        stmt = select(
            BotKnowledgeBaseModel.bot_id,
            BotKnowledgeBaseModel.knowledge_base_id,
        ).where(BotKnowledgeBaseModel.bot_id.in_(bot_ids))
        result = await self._session.execute(stmt)
        kb_map: dict[str, list[str]] = {bid: [] for bid in bot_ids}
        for row in result.all():
            kb_map[row.bot_id].append(row.knowledge_base_id)
        return kb_map

    async def _sync_kb_ids(
        self, bot_id: str, kb_ids: list[str]
    ) -> None:
        await self._session.execute(
            delete(BotKnowledgeBaseModel).where(
                BotKnowledgeBaseModel.bot_id == bot_id
            )
        )
        for kb_id in kb_ids:
            self._session.add(
                BotKnowledgeBaseModel(
                    bot_id=bot_id,
                    knowledge_base_id=kb_id,
                )
            )

    async def save(self, bot: Bot) -> None:
        async with atomic(self._session):
            existing = await self._session.get(BotModel, bot.id.value)
            if existing:
                existing.name = bot.name
                existing.description = bot.description
                existing.is_active = bot.is_active
                existing.system_prompt = bot.system_prompt
                existing.enabled_tools = bot.enabled_tools
                existing.llm_provider = bot.llm_provider
                existing.llm_model = bot.llm_model
                existing.show_sources = bot.show_sources
                existing.agent_mode = bot.agent_mode
                existing.mcp_servers = [
                    {
                        "url": s.url,
                        "name": s.name,
                        "enabled_tools": s.enabled_tools,
                        "tools": [
                            {"name": t.name, "description": t.description}
                            for t in s.tools
                        ],
                        "version": s.version,
                    }
                    for s in bot.mcp_servers
                ]
                existing.mcp_bindings = [
                    {
                        "registry_id": b.registry_id,
                        "enabled_tools": b.enabled_tools,
                        "env_values": b.env_values,
                    }
                    for b in bot.mcp_bindings
                ]
                existing.max_tool_calls = bot.max_tool_calls
                existing.audit_mode = bot.audit_mode
                existing.eval_provider = bot.eval_provider
                existing.eval_model = bot.eval_model
                existing.eval_depth = bot.eval_depth
                existing.base_prompt = bot.base_prompt
                existing.router_prompt = bot.router_prompt
                existing.react_prompt = bot.react_prompt
                existing.widget_enabled = bot.widget_enabled
                existing.widget_allowed_origins = bot.widget_allowed_origins
                existing.widget_keep_history = bot.widget_keep_history
                existing.avatar_type = bot.avatar_type
                existing.avatar_model_url = bot.avatar_model_url
                existing.widget_welcome_message = bot.widget_welcome_message
                existing.widget_placeholder_text = bot.widget_placeholder_text
                existing.widget_greeting_messages = bot.widget_greeting_messages
                existing.widget_greeting_animation = bot.widget_greeting_animation
                existing.line_channel_secret = bot.line_channel_secret
                existing.line_channel_access_token = bot.line_channel_access_token
                existing.temperature = bot.llm_params.temperature
                existing.max_tokens = bot.llm_params.max_tokens
                existing.history_limit = bot.llm_params.history_limit
                existing.frequency_penalty = bot.llm_params.frequency_penalty
                existing.reasoning_effort = bot.llm_params.reasoning_effort
                existing.rag_top_k = bot.llm_params.rag_top_k
                existing.rag_score_threshold = bot.llm_params.rag_score_threshold
                existing.updated_at = datetime.now(timezone.utc)
            else:
                model = BotModel(
                    id=bot.id.value,
                    short_code=bot.short_code.value,
                    tenant_id=bot.tenant_id,
                    name=bot.name,
                    description=bot.description,
                    is_active=bot.is_active,
                    system_prompt=bot.system_prompt,
                    enabled_tools=bot.enabled_tools,
                    llm_provider=bot.llm_provider,
                    llm_model=bot.llm_model,
                    show_sources=bot.show_sources,
                    agent_mode=bot.agent_mode,
                    mcp_servers=[
                        {
                            "url": s.url,
                            "name": s.name,
                            "enabled_tools": s.enabled_tools,
                            "tools": [
                                {"name": t.name, "description": t.description}
                                for t in s.tools
                            ],
                            "version": s.version,
                        }
                        for s in bot.mcp_servers
                    ],
                    mcp_bindings=[
                        {
                            "registry_id": b.registry_id,
                            "enabled_tools": b.enabled_tools,
                            "env_values": b.env_values,
                        }
                        for b in bot.mcp_bindings
                    ],
                    max_tool_calls=bot.max_tool_calls,
                    audit_mode=bot.audit_mode,
                    eval_provider=bot.eval_provider,
                    eval_model=bot.eval_model,
                    eval_depth=bot.eval_depth,
                    base_prompt=bot.base_prompt,
                    router_prompt=bot.router_prompt,
                    react_prompt=bot.react_prompt,
                    widget_enabled=bot.widget_enabled,
                    widget_allowed_origins=bot.widget_allowed_origins,
                    widget_keep_history=bot.widget_keep_history,
                    avatar_type=bot.avatar_type,
                    avatar_model_url=bot.avatar_model_url,
                    widget_welcome_message=bot.widget_welcome_message,
                    widget_placeholder_text=bot.widget_placeholder_text,
                    widget_greeting_messages=bot.widget_greeting_messages,
                    widget_greeting_animation=bot.widget_greeting_animation,
                    line_channel_secret=bot.line_channel_secret,
                    line_channel_access_token=bot.line_channel_access_token,
                    temperature=bot.llm_params.temperature,
                    max_tokens=bot.llm_params.max_tokens,
                    history_limit=bot.llm_params.history_limit,
                    frequency_penalty=bot.llm_params.frequency_penalty,
                    reasoning_effort=bot.llm_params.reasoning_effort,
                    rag_top_k=bot.llm_params.rag_top_k,
                    rag_score_threshold=bot.llm_params.rag_score_threshold,
                    created_at=bot.created_at,
                    updated_at=bot.updated_at,
                )
                self._session.add(model)

            await self._sync_kb_ids(bot.id.value, bot.knowledge_base_ids)

    async def find_by_id(self, bot_id: str) -> Bot | None:
        stmt = select(BotModel).where(BotModel.id == bot_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        kb_map = await self._get_all_kb_ids([bot_id])
        return self._to_entity(model, kb_map.get(bot_id, []))

    async def find_by_short_code(self, short_code: str) -> Bot | None:
        stmt = select(BotModel).where(BotModel.short_code == short_code)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        kb_map = await self._get_all_kb_ids([model.id])
        return self._to_entity(model, kb_map.get(model.id, []))

    async def find_all(self) -> list[Bot]:
        stmt = (
            select(BotModel)
            .options(selectinload(BotModel.knowledge_bases))
            .order_by(BotModel.created_at)
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())
        if not models:
            return []
        return [
            self._to_entity(
                m, [kb.knowledge_base_id for kb in m.knowledge_bases]
            )
            for m in models
        ]

    async def find_all_by_tenant(self, tenant_id: str) -> list[Bot]:
        stmt = (
            select(BotModel)
            .options(selectinload(BotModel.knowledge_bases))
            .where(BotModel.tenant_id == tenant_id)
            .order_by(BotModel.created_at)
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())
        if not models:
            return []
        return [
            self._to_entity(
                m, [kb.knowledge_base_id for kb in m.knowledge_bases]
            )
            for m in models
        ]

    async def delete(self, bot_id: str) -> None:
        async with atomic(self._session):
            await self._session.execute(
                delete(BotKnowledgeBaseModel).where(
                    BotKnowledgeBaseModel.bot_id == bot_id
                )
            )
            await self._session.execute(
                delete(BotModel).where(BotModel.id == bot_id)
            )
