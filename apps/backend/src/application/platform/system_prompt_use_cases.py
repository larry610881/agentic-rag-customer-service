"""系統提示詞 CRUD 用例"""

from dataclasses import dataclass
from datetime import datetime, timezone

from src.domain.platform.entity import SystemPromptConfig
from src.domain.platform.repository import SystemPromptConfigRepository


class GetSystemPromptsUseCase:
    def __init__(
        self, system_prompt_config_repository: SystemPromptConfigRepository
    ) -> None:
        self._repo = system_prompt_config_repository

    async def execute(self) -> SystemPromptConfig:
        return await self._repo.get()


@dataclass(frozen=True)
class UpdateSystemPromptsCommand:
    system_prompt: str = ""


class UpdateSystemPromptsUseCase:
    def __init__(
        self, system_prompt_config_repository: SystemPromptConfigRepository
    ) -> None:
        self._repo = system_prompt_config_repository

    async def execute(
        self, command: UpdateSystemPromptsCommand
    ) -> SystemPromptConfig:
        config = await self._repo.get()
        config.system_prompt = command.system_prompt
        config.updated_at = datetime.now(timezone.utc)
        await self._repo.save(config)
        return config
