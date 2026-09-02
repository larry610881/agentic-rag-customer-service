from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.domain.memory.entity import MemoryFact


@dataclass(frozen=True)
class ExtractedFact:
    """A single fact extracted from a conversation by LLM."""

    category: str
    key: str
    value: str
    confidence: float = 1.0


class MemoryExtractionService(ABC):
    @abstractmethod
    async def extract_facts(
        self,
        conversation_messages: list[dict[str, str]],
        existing_facts: list[MemoryFact],
        extraction_prompt: str = "",
        usage_collector: dict[str, Any] | None = None,
    ) -> list[ExtractedFact]:
        """Extract memorable facts from conversation using LLM.

        Issue #59：``usage_collector`` 非 None 時實作回填 ``{"usage": TokenUsage}``，
        讓 use case 能記帳（與 LLMService.generate_stream 的 usage_collector 同慣例）。
        """
        ...


@dataclass
class MemoryContext:
    """Formatted memory context ready for LLM injection."""

    facts: list[MemoryFact] = field(default_factory=list)
    formatted_prompt: str = ""

    @property
    def has_memory(self) -> bool:
        return bool(self.facts)
