from dataclasses import dataclass

from src.domain.security.guard_config import GuardRulesConfig, GuardRulesConfigRepository
from src.application.security.prompt_guard_service import (
    DEFAULT_INPUT_RULES,
    DEFAULT_OUTPUT_KEYWORDS,
    DEFAULT_INPUT_GUARD_PROMPT,
    DEFAULT_OUTPUT_GUARD_PROMPT,
)


class GetGuardRulesUseCase:
    def __init__(self, repo: GuardRulesConfigRepository) -> None:
        self._repo = repo

    async def execute(self) -> GuardRulesConfig:
        config = await self._repo.get()
        if config is None:
            return GuardRulesConfig(
                input_rules=DEFAULT_INPUT_RULES,
                output_keywords=DEFAULT_OUTPUT_KEYWORDS,
                input_guard_prompt=DEFAULT_INPUT_GUARD_PROMPT,
                output_guard_prompt=DEFAULT_OUTPUT_GUARD_PROMPT,
            )
        return config


@dataclass(frozen=True)
class UpdateGuardRulesCommand:
    input_rules: list[dict]
    output_keywords: list[dict]
    llm_guard_enabled: bool = False
    llm_guard_model: str = ""
    input_guard_prompt: str = ""
    output_guard_prompt: str = ""
    blocked_response: str = "我只能協助您處理客服相關問題。"


class UpdateGuardRulesUseCase:
    def __init__(self, repo: GuardRulesConfigRepository) -> None:
        self._repo = repo

    async def execute(self, command: UpdateGuardRulesCommand) -> GuardRulesConfig:
        config = GuardRulesConfig(
            id="default",
            input_rules=command.input_rules,
            output_keywords=command.output_keywords,
            llm_guard_enabled=command.llm_guard_enabled,
            llm_guard_model=command.llm_guard_model,
            input_guard_prompt=command.input_guard_prompt,
            output_guard_prompt=command.output_guard_prompt,
            blocked_response=command.blocked_response,
        )
        await self._repo.save(config)
        return config


class ResetGuardRulesUseCase:
    def __init__(self, repo: GuardRulesConfigRepository) -> None:
        self._repo = repo

    async def execute(self) -> GuardRulesConfig:
        config = GuardRulesConfig(
            id="default",
            input_rules=DEFAULT_INPUT_RULES,
            output_keywords=DEFAULT_OUTPUT_KEYWORDS,
            input_guard_prompt=DEFAULT_INPUT_GUARD_PROMPT,
            output_guard_prompt=DEFAULT_OUTPUT_GUARD_PROMPT,
        )
        await self._repo.save(config)
        return config
