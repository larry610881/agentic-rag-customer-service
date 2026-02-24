"""建立機器人用例"""

from dataclasses import dataclass, field

from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.repository import BotRepository


@dataclass(frozen=True)
class CreateBotCommand:
    tenant_id: str
    name: str
    description: str = ""
    knowledge_base_ids: list[str] = field(default_factory=list)
    system_prompt: str = ""
    is_active: bool = True
    temperature: float = 0.3
    max_tokens: int = 1024
    history_limit: int = 10
    frequency_penalty: float = 0.0
    reasoning_effort: str = "medium"
    enabled_tools: list[str] = field(default_factory=lambda: ["rag_query"])
    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None


class CreateBotUseCase:
    def __init__(self, bot_repository: BotRepository) -> None:
        self._bot_repo = bot_repository

    async def execute(self, command: CreateBotCommand) -> Bot:
        bot = Bot(
            tenant_id=command.tenant_id,
            name=command.name,
            description=command.description,
            is_active=command.is_active,
            system_prompt=command.system_prompt,
            knowledge_base_ids=list(command.knowledge_base_ids),
            llm_params=BotLLMParams(
                temperature=command.temperature,
                max_tokens=command.max_tokens,
                history_limit=command.history_limit,
                frequency_penalty=command.frequency_penalty,
                reasoning_effort=command.reasoning_effort,
            ),
            enabled_tools=list(command.enabled_tools),
            line_channel_secret=command.line_channel_secret,
            line_channel_access_token=command.line_channel_access_token,
        )
        await self._bot_repo.save(bot)
        return bot
