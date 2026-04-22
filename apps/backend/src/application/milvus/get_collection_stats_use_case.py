"""Get Collection Stats Use Case — S-KB-Studio.1"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.domain.rag.services import VectorStore


@dataclass(frozen=True)
class GetCollectionStatsQuery:
    collection_name: str
    # tenant boundary validation done in router (with kb_repo) — UC 單純讀


class GetCollectionStatsUseCase:
    def __init__(self, vector_store: VectorStore) -> None:
        self._vs = vector_store

    async def execute(
        self, query: GetCollectionStatsQuery
    ) -> dict[str, Any]:
        return await self._vs.get_collection_stats(query.collection_name)
