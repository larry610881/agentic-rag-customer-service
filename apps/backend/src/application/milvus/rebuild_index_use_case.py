"""Rebuild Milvus Scalar Index Use Case — S-KB-Studio.1

對應既有 scripts/rebuild_milvus_scalar_index.py 的單 collection 版本，
提供 admin API 用於新建 collection 後的 INVERTED index 重建。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from src.domain.rag.services import VectorStore

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RebuildIndexCommand:
    collection_name: str
    actor: str = ""


class RebuildIndexUseCase:
    def __init__(self, vector_store: VectorStore) -> None:
        self._vs = vector_store

    async def execute(
        self, command: RebuildIndexCommand
    ) -> dict[str, Any]:
        # 具體 rebuild 動作由 VectorStore.rebuild_scalar_indexes 實作
        # (infrastructure/milvus 端加，預設空操作)
        rebuilder = getattr(self._vs, "rebuild_scalar_indexes", None)
        if rebuilder is None:
            logger.warning(
                "milvus.rebuild_index.not_supported",
                collection=command.collection_name,
            )
            return {"status": "not_supported", "collection": command.collection_name}

        result = await rebuilder(command.collection_name)
        logger.info(
            "kb_studio.milvus.rebuild_index",
            collection=command.collection_name,
            actor=command.actor,
            result=result,
        )
        return {"status": "ok", "collection": command.collection_name, **result}
