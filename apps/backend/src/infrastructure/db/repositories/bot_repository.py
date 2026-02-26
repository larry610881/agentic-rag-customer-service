from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
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
            line_channel_secret=model.line_channel_secret,
            line_channel_access_token=model.line_channel_access_token,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def _get_kb_ids(self, bot_id: str) -> list[str]:
        stmt = select(BotKnowledgeBaseModel.knowledge_base_id).where(
            BotKnowledgeBaseModel.bot_id == bot_id
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

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
        existing = await self._session.get(BotModel, bot.id.value)
        if existing:
            existing.name = bot.name
            existing.description = bot.description
            existing.is_active = bot.is_active
            existing.system_prompt = bot.system_prompt
            existing.enabled_tools = bot.enabled_tools
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
                tenant_id=bot.tenant_id,
                name=bot.name,
                description=bot.description,
                is_active=bot.is_active,
                system_prompt=bot.system_prompt,
                enabled_tools=bot.enabled_tools,
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
        await self._session.commit()

    async def find_by_id(self, bot_id: str) -> Bot | None:
        stmt = select(BotModel).where(BotModel.id == bot_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        kb_ids = await self._get_kb_ids(bot_id)
        return self._to_entity(model, kb_ids)

    async def find_all_by_tenant(self, tenant_id: str) -> list[Bot]:
        stmt = (
            select(BotModel)
            .where(BotModel.tenant_id == tenant_id)
            .order_by(BotModel.created_at)
        )
        result = await self._session.execute(stmt)
        bots = []
        for model in result.scalars().all():
            kb_ids = await self._get_kb_ids(model.id)
            bots.append(self._to_entity(model, kb_ids))
        return bots

    async def delete(self, bot_id: str) -> None:
        await self._session.execute(
            delete(BotKnowledgeBaseModel).where(
                BotKnowledgeBaseModel.bot_id == bot_id
            )
        )
        await self._session.execute(
            delete(BotModel).where(BotModel.id == bot_id)
        )
        await self._session.commit()
