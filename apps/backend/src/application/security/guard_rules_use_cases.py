from dataclasses import dataclass
from typing import Any

from src.application.security.prompt_guard_service import (
    DEFAULT_INPUT_GUARD_PROMPT,
    DEFAULT_INPUT_RULES,
    DEFAULT_OUTPUT_GUARD_PROMPT,
    DEFAULT_OUTPUT_KEYWORDS,
)
from src.domain.security.guard_config import (
    GuardRulesConfig,
    GuardRulesConfigRepository,
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
    llm_input_guard_enabled: bool = False
    llm_guard_model: str = ""
    input_guard_prompt: str = ""
    output_guard_prompt: str = ""
    blocked_response: str = "我只能協助您處理客服相關問題。"
    actor_user_id: str | None = None  # Issue #60：稽核 actor


def _guard_view(cfg: GuardRulesConfig | None) -> dict | None:
    """Issue #60：稽核用可比較視圖。"""
    if cfg is None:
        return None
    return {
        "input_rules": cfg.input_rules,
        "output_keywords": cfg.output_keywords,
        "llm_guard_enabled": cfg.llm_guard_enabled,
        "llm_input_guard_enabled": cfg.llm_input_guard_enabled,
        "llm_guard_model": cfg.llm_guard_model,
        "input_guard_prompt": cfg.input_guard_prompt,
        "output_guard_prompt": cfg.output_guard_prompt,
        "blocked_response": cfg.blocked_response,
    }


class UpdateGuardRulesUseCase:
    def __init__(
        self, repo: GuardRulesConfigRepository, audit: Any | None = None
    ) -> None:
        self._repo = repo
        self._audit = audit

    async def execute(self, command: UpdateGuardRulesCommand) -> GuardRulesConfig:
        before = _guard_view(await self._repo.get()) if self._audit else None
        config = GuardRulesConfig(
            id="default",
            input_rules=command.input_rules,
            output_keywords=command.output_keywords,
            llm_guard_enabled=command.llm_guard_enabled,
            llm_input_guard_enabled=command.llm_input_guard_enabled,
            llm_guard_model=command.llm_guard_model,
            input_guard_prompt=command.input_guard_prompt,
            output_guard_prompt=command.output_guard_prompt,
            blocked_response=command.blocked_response,
        )
        await self._repo.save(config)
        if self._audit is not None:
            await self._audit.record(
                entity_type="guard_rules", entity_id=config.id, action="update",
                before=before, after=_guard_view(config),
                actor_user_id=command.actor_user_id,
            )
        return config


class ResetGuardRulesUseCase:
    def __init__(
        self, repo: GuardRulesConfigRepository, audit: Any | None = None
    ) -> None:
        self._repo = repo
        self._audit = audit

    async def execute(self, actor_user_id: str | None = None) -> GuardRulesConfig:
        before = _guard_view(await self._repo.get()) if self._audit else None
        config = GuardRulesConfig(
            id="default",
            input_rules=DEFAULT_INPUT_RULES,
            output_keywords=DEFAULT_OUTPUT_KEYWORDS,
            input_guard_prompt=DEFAULT_INPUT_GUARD_PROMPT,
            output_guard_prompt=DEFAULT_OUTPUT_GUARD_PROMPT,
        )
        await self._repo.save(config)
        if self._audit is not None:
            await self._audit.record(
                entity_type="guard_rules", entity_id=config.id, action="reset",
                before=before, after=_guard_view(config), actor_user_id=actor_user_id,
            )
        return config
