"""Auto-classification via embedding clustering + LLM naming.

Steps:
1. Fetch all vectors from Milvus for a KB
2. AgglomerativeClustering (auto k via distance_threshold)
3. For each cluster, pick representative chunk samples
4. LLM names the cluster
5. Return categories + chunk-to-category mapping
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone
from typing import Callable, Awaitable

import numpy as np
from sklearn.cluster import AgglomerativeClustering

import anthropic

from src.domain.knowledge.entity import ChunkCategory
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

NAMING_PROMPT = """\
以下是同一群組中的幾個文件片段：

{samples}

請根據這些片段的共同主題，生成一個簡短的分類名稱（3-8 個字，繁體中文）。
只輸出分類名稱，不要其他內容。"""

DEFAULT_MODEL = "claude-sonnet-4-6-20260415"
SAMPLES_PER_CLUSTER = 5
MIN_CHUNKS_FOR_CLUSTERING = 5
MAX_CLUSTERS = 20


class ClusterClassificationService:
    def __init__(
        self,
        api_key: str = "",
        api_key_resolver: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_key_resolver = api_key_resolver
        self._client: anthropic.AsyncAnthropic | None = None

    async def _ensure_client(self) -> anthropic.AsyncAnthropic:
        if self._client is not None:
            return self._client
        api_key = self._api_key
        if not api_key and self._api_key_resolver:
            api_key = await self._api_key_resolver("anthropic")
        if not api_key:
            raise RuntimeError("No Anthropic API key for classification")
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        return self._client

    async def classify(
        self,
        chunk_ids: list[str],
        chunk_contents: list[str],
        vectors: list[list[float]],
        kb_id: str,
        tenant_id: str,
        model: str = "",
    ) -> tuple[list[ChunkCategory], dict[str, str]]:
        """Classify chunks into categories.

        Returns:
            (categories, chunk_to_category_map)
            chunk_to_category_map: {chunk_id: category_id}
        """
        if len(chunk_ids) < MIN_CHUNKS_FOR_CLUSTERING:
            logger.info("classification.skip", reason="too_few_chunks", count=len(chunk_ids))
            return [], {}

        model = model or DEFAULT_MODEL
        if ":" in model:
            model = model.split(":", 1)[1]

        log = logger.bind(kb_id=kb_id, model=model, chunk_count=len(chunk_ids))
        log.info("classification.start")

        # 1. Cluster
        X = np.array(vectors)
        n_clusters = min(MAX_CLUSTERS, max(2, len(chunk_ids) // 10))
        clustering = AgglomerativeClustering(n_clusters=n_clusters)
        labels = clustering.fit_predict(X)

        # 2. Group chunks by cluster
        clusters: dict[int, list[int]] = {}
        for idx, label in enumerate(labels):
            clusters.setdefault(int(label), []).append(idx)

        log.info("classification.clustered", n_clusters=len(clusters))

        # 3. Name each cluster
        client = await self._ensure_client()
        categories: list[ChunkCategory] = []
        chunk_to_cat: dict[str, str] = {}

        async def _name_cluster(label: int, indices: list[int]) -> None:
            cat_id = str(uuid.uuid4())
            # Pick representative samples
            sample_indices = random.sample(
                indices, min(SAMPLES_PER_CLUSTER, len(indices))
            )
            samples_text = "\n---\n".join(
                chunk_contents[i][:300] for i in sample_indices
            )

            try:
                resp = await client.messages.create(
                    model=model,
                    max_tokens=50,
                    messages=[{
                        "role": "user",
                        "content": NAMING_PROMPT.format(samples=samples_text),
                    }],
                )
                name = resp.content[0].text.strip()[:200]
            except Exception:
                log.warning("classification.naming_failed", label=label, exc_info=True)
                name = f"分類 {label + 1}"

            now = datetime.now(timezone.utc)
            categories.append(ChunkCategory(
                id=cat_id,
                kb_id=kb_id,
                tenant_id=tenant_id,
                name=name,
                chunk_count=len(indices),
                created_at=now,
                updated_at=now,
            ))
            for idx in indices:
                chunk_to_cat[chunk_ids[idx]] = cat_id

        await asyncio.gather(*[
            _name_cluster(label, indices)
            for label, indices in clusters.items()
        ])

        log.info("classification.done", categories=len(categories))
        return categories, chunk_to_cat
