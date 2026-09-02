"""記憶萃取用例 — 從對話中萃取事實並 upsert 到 memory_facts"""

from dataclasses import dataclass
from typing import Any

import structlog

from src.domain.memory.entity import MemoryFact
from src.domain.memory.repository import MemoryFactRepository
from src.domain.memory.services import MemoryExtractionService
from src.domain.memory.value_objects import MemoryFactId

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ExtractMemoryCommand:
    profile_id: str
    tenant_id: str
    conversation_id: str
    messages: list[dict[str, str]]  # [{"role": "user", "content": "..."}, ...]
    extraction_prompt: str = ""


class ExtractMemoryUseCase:
    async def _record_extraction_usage(
        self, tenant_id: str, usage_collector: dict[str, Any]
    ) -> None:
        usage = usage_collector.get("usage")
        if self._record_usage is None or usage is None:
            return
        from src.domain.usage.category import UsageCategory

        try:
            await self._record_usage.execute(
                tenant_id=tenant_id,
                request_type=UsageCategory.MEMORY_EXTRACTION.value,
                usage=usage,
            )
        except Exception:
            logger.warning("memory.extraction.usage_record_failed", exc_info=True)

    def __init__(
        self,
        memory_fact_repository: MemoryFactRepository,
        extraction_service: MemoryExtractionService,
        record_usage: Any | None = None,
    ) -> None:
        self._fact_repo = memory_fact_repository
        self._extraction_service = extraction_service
        # Issue #59：萃取 LLM 呼叫原本沒記帳
        self._record_usage = record_usage

    async def execute(self, command: ExtractMemoryCommand) -> int:
        """Extract facts from conversation and upsert to DB.

        Returns:
            Number of facts upserted.
        """
        # Load existing facts to avoid duplicates
        existing = await self._fact_repo.find_by_profile(
            profile_id=command.profile_id,
            include_expired=True,
        )

        # Extract new facts via LLM
        usage_collector: dict[str, Any] = {}
        extracted = await self._extraction_service.extract_facts(
            conversation_messages=command.messages,
            existing_facts=existing,
            extraction_prompt=command.extraction_prompt,
            usage_collector=usage_collector,
        )
        await self._record_extraction_usage(command.tenant_id, usage_collector)

        if not extracted:
            logger.debug(
                "memory.extraction.no_facts",
                profile_id=command.profile_id,
                conversation_id=command.conversation_id,
            )
            return 0

        # Upsert each fact
        upserted = 0
        for fact_data in extracted:
            fact = MemoryFact(
                id=MemoryFactId(),
                profile_id=command.profile_id,
                tenant_id=command.tenant_id,
                memory_type="long_term",
                category=fact_data.category,
                key=fact_data.key,
                value=fact_data.value,
                source_conversation_id=command.conversation_id,
                confidence=fact_data.confidence,
            )
            await self._fact_repo.upsert_by_key(fact)
            upserted += 1

        logger.info(
            "memory.extraction.completed",
            profile_id=command.profile_id,
            conversation_id=command.conversation_id,
            facts_upserted=upserted,
        )
        return upserted
