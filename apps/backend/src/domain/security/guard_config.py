from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class GuardRulesConfig:
    """Singleton config for Prompt Injection Guard rules."""

    id: str = "default"
    input_rules: list[dict] = field(default_factory=list)
    output_keywords: list[dict] = field(default_factory=list)
    llm_guard_enabled: bool = False
    llm_guard_model: str = ""
    input_guard_prompt: str = ""
    output_guard_prompt: str = ""
    blocked_response: str = "我只能協助您處理客服相關問題。"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True)
class GuardResult:
    passed: bool
    blocked_response: str | None = None
    rule_matched: str | None = None


class GuardRulesConfigRepository(ABC):
    @abstractmethod
    async def get(self) -> GuardRulesConfig | None: ...

    @abstractmethod
    async def save(self, config: GuardRulesConfig) -> None: ...


class GuardLogRepository(ABC):
    @abstractmethod
    async def save_log(
        self,
        tenant_id: str,
        bot_id: str | None,
        user_id: str | None,
        log_type: str,
        rule_matched: str,
        user_message: str,
        ai_response: str | None,
    ) -> None: ...

    @abstractmethod
    async def find_logs(
        self,
        *,
        tenant_id: str | None = None,
        log_type: str | None = None,
        bot_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]: ...

    @abstractmethod
    async def count_logs(
        self,
        *,
        tenant_id: str | None = None,
        log_type: str | None = None,
        bot_id: str | None = None,
    ) -> int: ...
