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
from typing import Awaitable, Callable

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from src.domain.knowledge.entity import ChunkCategory
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

# S-LLM-Cache.1: 拆 system instruction (cacheable) + user samples (volatile)。
# 註：instruction 較短可能低於某些 provider 的最小 cacheable 尺寸（Anthropic Sonnet
# 1024 / Haiku 2048 token），那種情況下 marker 被忽略 = 不省也不害。
_NAMING_SYSTEM_PROMPT = """\
你的任務：根據幾個文件片段，生成一個簡短的繁體中文分類名稱。
要求：3-8 個字、只輸出分類名稱、不要其他內容。"""

_NAMING_USER_TEMPLATE = """\
以下是同一群組中的幾個文件片段：

{samples}

請依上述要求生成分類名稱。"""

DEFAULT_MODEL = "anthropic:claude-sonnet-4-6-20260415"
SAMPLES_PER_CLUSTER = 5
MIN_CHUNKS_FOR_CLUSTERING = 5
MAX_CLUSTERS = 20


class ClusterClassificationService:
    def __init__(
        self,
        api_key: str = "",
        api_key_resolver: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        self._api_key_resolver = api_key_resolver
        # Token-Gov.0: 累計每次 classify 的 LLM token 用量
        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0
        # S-LLM-Cache.1: cache-aware token tracking
        self.last_cache_read_tokens: int = 0
        self.last_cache_creation_tokens: int = 0
        self.last_model: str = ""

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

        # Token-Gov.0: 重置 token 累計（S-LLM-Cache.1 含 cache 欄位）
        self.last_input_tokens = 0
        self.last_output_tokens = 0
        self.last_cache_read_tokens = 0
        self.last_cache_creation_tokens = 0

        model = model or DEFAULT_MODEL
        self.last_model = model
        # Don't strip provider prefix — call_llm handles "provider:model" format

        log = logger.bind(kb_id=kb_id, model=model, chunk_count=len(chunk_ids))
        log.info("classification.start")

        # 1. Cluster — let algorithm decide optimal number
        X = np.array(vectors)
        # Use distance_threshold with cosine metric.
        # Cosine distance range: 0 (identical) ~ 2 (opposite).
        # 0.5 = chunks with cosine similarity > 0.75 grouped together.
        # Target: ~5-10 categories for typical KB sizes.
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=0.5,
            metric="cosine",
            linkage="average",
        )
        labels = clustering.fit_predict(X)

        # Guard: too many small clusters → re-cluster with capped n
        unique_labels = set(labels)
        max_reasonable = min(MAX_CLUSTERS, max(3, len(chunk_ids) // 5))
        if len(unique_labels) > max_reasonable:
            clustering = AgglomerativeClustering(n_clusters=max_reasonable)
            labels = clustering.fit_predict(X)

        # 2. Group chunks by cluster
        clusters: dict[int, list[int]] = {}
        for idx, label in enumerate(labels):
            clusters.setdefault(int(label), []).append(idx)

        log.info("classification.clustered", n_clusters=len(clusters))

        # 3. Name each cluster
        from src.domain.llm import BlockRole, CacheHint, PromptBlock
        from src.infrastructure.llm.llm_caller import call_llm

        # S-LLM-Cache.1: 預組固定 system block，多 cluster 並發時利用 cache
        system_block = PromptBlock(
            text=_NAMING_SYSTEM_PROMPT,
            role=BlockRole.SYSTEM,
            cache=CacheHint.EPHEMERAL,
        )

        categories: list[ChunkCategory] = []
        chunk_to_cat: dict[str, str] = {}

        async def _name_cluster(label: int, indices: list[int]) -> None:
            cat_id = str(uuid.uuid4())
            sample_indices = random.sample(
                indices, min(SAMPLES_PER_CLUSTER, len(indices))
            )
            samples_text = "\n---\n".join(
                chunk_contents[i][:300] for i in sample_indices
            )

            try:
                result = await call_llm(
                    model_spec=model,
                    prompt=[
                        system_block,
                        PromptBlock(
                            text=_NAMING_USER_TEMPLATE.format(samples=samples_text),
                            role=BlockRole.USER,
                            cache=CacheHint.NONE,
                        ),
                    ],
                    max_tokens=50,
                    api_key_resolver=self._api_key_resolver,
                )
                name = result.text[:200]
                # Token-Gov.0: 累計（asyncio.gather 並發但群組數一般 < 20，
                # CPython int 加法 GIL 安全）
                # S-LLM-Cache.1: 含 cache 欄位
                self.last_input_tokens += result.input_tokens
                self.last_output_tokens += result.output_tokens
                self.last_cache_read_tokens += result.cache_read_tokens
                self.last_cache_creation_tokens += result.cache_creation_tokens
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
