"""系統提示詞 CRUD 用例"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

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
    actor_user_id: str | None = None  # Issue #60：稽核 actor


class UpdateSystemPromptsUseCase:
    def __init__(
        self,
        system_prompt_config_repository: SystemPromptConfigRepository,
        audit: Any | None = None,
    ) -> None:
        self._repo = system_prompt_config_repository
        self._audit = audit

    async def execute(
        self, command: UpdateSystemPromptsCommand
    ) -> SystemPromptConfig:
        config = await self._repo.get()
        before = {"system_prompt": config.system_prompt}
        config.system_prompt = command.system_prompt
        config.updated_at = datetime.now(timezone.utc)
        await self._repo.save(config)
        if self._audit is not None:
            await self._audit.record(
                entity_type="system_prompt", entity_id=config.id, action="update",
                before=before, after={"system_prompt": config.system_prompt},
                actor_user_id=command.actor_user_id,
            )
        return config
