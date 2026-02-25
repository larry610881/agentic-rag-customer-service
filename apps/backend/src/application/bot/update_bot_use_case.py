"""更新機器人用例"""

from dataclasses import dataclass, replace

from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.repository import BotRepository
from src.domain.shared.exceptions import EntityNotFoundError

_UNSET = object()


@dataclass(frozen=True)
class UpdateBotCommand:
    bot_id: str
    name: object = _UNSET
    description: object = _UNSET
    is_active: object = _UNSET
    knowledge_base_ids: object = _UNSET
    system_prompt: object = _UNSET
    temperature: object = _UNSET
    max_tokens: object = _UNSET
    history_limit: object = _UNSET
    frequency_penalty: object = _UNSET
    reasoning_effort: object = _UNSET
    rag_top_k: object = _UNSET
    rag_score_threshold: object = _UNSET
    enabled_tools: object = _UNSET
    line_channel_secret: object = _UNSET
    line_channel_access_token: object = _UNSET


class UpdateBotUseCase:
    def __init__(self, bot_repository: BotRepository) -> None:
        self._bot_repo = bot_repository

    async def execute(self, command: UpdateBotCommand) -> Bot:
        bot = await self._bot_repo.find_by_id(command.bot_id)
        if bot is None:
            raise EntityNotFoundError("Bot", command.bot_id)

        if command.name is not _UNSET:
            bot.name = command.name  # type: ignore[assignment]
        if command.description is not _UNSET:
            bot.description = command.description  # type: ignore[assignment]
        if command.is_active is not _UNSET:
            bot.is_active = command.is_active  # type: ignore[assignment]
        if command.knowledge_base_ids is not _UNSET:
            bot.knowledge_base_ids = list(command.knowledge_base_ids)  # type: ignore[arg-type]
        if command.system_prompt is not _UNSET:
            bot.system_prompt = command.system_prompt  # type: ignore[assignment]
        if command.enabled_tools is not _UNSET:
            bot.enabled_tools = list(command.enabled_tools)  # type: ignore[arg-type]
        if command.line_channel_secret is not _UNSET:
            bot.line_channel_secret = command.line_channel_secret  # type: ignore[assignment]
        if command.line_channel_access_token is not _UNSET:
            bot.line_channel_access_token = command.line_channel_access_token  # type: ignore[assignment]

        # LLM params — collect changed fields, apply once via replace()
        _LLM_FIELDS = (
            "temperature", "max_tokens", "history_limit",
            "frequency_penalty", "reasoning_effort",
            "rag_top_k", "rag_score_threshold",
        )
        llm_changes = {
            k: getattr(command, k)
            for k in _LLM_FIELDS
            if getattr(command, k) is not _UNSET
        }
        if llm_changes:
            bot.llm_params = replace(bot.llm_params, **llm_changes)

        await self._bot_repo.save(bot)
        return bot
