"""載入記憶用例 — 讀取用戶長期記憶並格式化為 prompt"""

from dataclasses import dataclass

import structlog

from src.domain.memory.entity import MemoryFact
from src.domain.memory.repository import MemoryFactRepository
from src.domain.memory.services import MemoryContext

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class LoadMemoryCommand:
    profile_id: str
    memory_type: str | None = None  # None = all types


class LoadMemoryUseCase:
    def __init__(
        self, memory_fact_repository: MemoryFactRepository
    ) -> None:
        self._fact_repo = memory_fact_repository

    async def execute(self, command: LoadMemoryCommand) -> MemoryContext:
        """Load memory facts for a visitor profile and format as prompt."""
        facts = await self._fact_repo.find_by_profile(
            profile_id=command.profile_id,
            memory_type=command.memory_type,
        )

        if not facts:
            return MemoryContext()

        formatted = self._format_facts(facts)
        logger.debug(
            "memory.loaded",
            profile_id=command.profile_id,
            fact_count=len(facts),
        )
        return MemoryContext(facts=facts, formatted_prompt=formatted)

    @staticmethod
    def _format_facts(facts: list[MemoryFact]) -> str:
        lines = ["[用戶記憶]"]
        for fact in facts:
            lines.append(f"- {fact.key}: {fact.value}")
        return "\n".join(lines)
