"""Milvus implementation of VectorStore."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from pymilvus import (
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
)

from src.domain.rag.services import VectorStore
from src.domain.rag.value_objects import SearchResult
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

# Fields extracted as first-class schema columns (the rest go into `extra` JSON)
_KNOWN_FIELDS = frozenset({
    "tenant_id", "document_id", "content", "chunk_index",
    "content_type", "language",
    # External producer integration: track which source produced the chunk so
    # we can dedup on re-ingest and cascade-delete when the source record is
    # removed.
    "source", "source_id",
})

_SAFE_VALUE_RE = re.compile(r'^[a-zA-Z0-9\-_.:/ ]+$')


def _sanitize_filter_value(value: Any) -> str:
    """Validate and quote a filter value to prevent expression injection."""
    s = str(value)
    if not _SAFE_VALUE_RE.match(s):
        raise ValueError(f"Unsafe filter value: {s!r}")
    return f'"{s}"'


def _build_filter_expr(filters: dict[str, Any]) -> str:
    """Convert filter dict to Milvus filter expression.

    - Scalar value → ``field == "value"``
    - List value   → ``field in ["v1", "v2", ...]``  (Milvus IN operator)

    Used for tenant_id / document_id / source / source_id and any future
    first-class fields. Values are sanitized to prevent expression injection.
    """
    parts = []
    for k, v in filters.items():
        if isinstance(v, list):
            sanitized = [_sanitize_filter_value(x) for x in v]
            parts.append(f'{k} in [{", ".join(sanitized)}]')
        else:
            parts.append(f'{k} == {_sanitize_filter_value(v)}')
    return " and ".join(parts)


def _build_schema(vector_size: int) -> CollectionSchema:
    """Build Milvus collection schema with fixed fields + JSON overflow."""
    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=128, is_primary=True),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=vector_size),
        FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
        FieldSchema(name="content_type", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="language", dtype=DataType.VARCHAR, max_length=16),
        # External producer integration (default "" so legacy rows backfilled
        # via add_field stay queryable but don't accidentally match real
        # producer source filters).
        FieldSchema(
            name="source",
            dtype=DataType.VARCHAR,
            max_length=64,
            default_value="",
        ),
        FieldSchema(
            name="source_id",
            dtype=DataType.VARCHAR,
            max_length=128,
            default_value="",
        ),
        FieldSchema(name="extra", dtype=DataType.JSON),
    ]
    return CollectionSchema(fields=fields, enable_dynamic_field=False)


def _safe_collection_name(name: str) -> str:
    """Milvus collection names allow only letters, digits, underscores."""
    return name.replace("-", "_")


class MilvusVectorStore(VectorStore):
    """VectorStore implementation backed by Milvus."""

    def __init__(
        self,
        uri: str = "http://localhost:19530",
        token: str = "",
        db_name: str = "default",
    ) -> None:
        self._client = MilvusClient(uri=uri, token=token or None, db_name=db_name)
        # Cache: collection_name -> set of field names actually present.
        # Filled lazily on first upsert/search per collection. Lets us strip
        # entity keys that the (possibly older / pre-Issue#44) collection
        # schema does not have, instead of crashing the whole upsert batch.
        self._schema_field_cache: dict[str, set[str]] = {}
        logger.info("milvus.init", uri=uri, db_name=db_name)

    async def _collection_field_names(self, collection: str) -> set[str]:
        """Return the set of field names defined on the given collection.

        Cached per-process. On error returns empty set so callers fall back
        to passing every entity key (worst case: same crash as today).
        """
        cached = self._schema_field_cache.get(collection)
        if cached is not None:
            return cached
        try:
            desc = await asyncio.to_thread(
                self._client.describe_collection, collection_name=collection
            )
            fields = desc.get("fields", []) if isinstance(desc, dict) else []
            names = {
                f.get("name") for f in fields if isinstance(f, dict)
            }
            names.discard(None)
            self._schema_field_cache[collection] = names  # type: ignore[assignment]
            return names  # type: ignore[return-value]
        except Exception:
            logger.warning(
                "milvus.describe_collection.failed",
                collection=collection,
                exc_info=True,
            )
            return set()

    async def ensure_collection(
        self, collection: str, vector_size: int
    ) -> None:
        collection = _safe_collection_name(collection)
        has = await asyncio.to_thread(self._client.has_collection, collection)
        if not has:
            schema = _build_schema(vector_size)
            index_params = self._client.prepare_index_params()
            index_params.add_index(
                field_name="vector",
                index_type="AUTOINDEX",
                metric_type="COSINE",
            )
            # S-KB-Studio.0 hotfix: 原本 index_type="" 等於沒建 scalar index，
            # tenant_id filter 每次走 full scan，隨資料量成長會雪崩。
            # INVERTED 適用字串欄位（Milvus 2.4+）。
            index_params.add_index(
                field_name="tenant_id", index_type="INVERTED"
            )
            index_params.add_index(
                field_name="document_id", index_type="INVERTED"
            )
            # External producer integration: source / source_id are high-frequency
            # filter targets (dedup on re-ingest, DELETE /by-source, search
            # filter). INVERTED index keeps them O(log n) instead of full scan.
            index_params.add_index(
                field_name="source", index_type="INVERTED"
            )
            index_params.add_index(
                field_name="source_id", index_type="INVERTED"
            )

            await asyncio.to_thread(
                self._client.create_collection,
                collection_name=collection,
                schema=schema,
                index_params=index_params,
            )
            logger.info(
                "milvus.collection.created",
                collection=collection,
                vector_size=vector_size,
            )
        else:
            # Ensure collection is loaded (required after Milvus restart)
            await asyncio.to_thread(self._client.load_collection, collection)
            logger.debug("milvus.collection.loaded", collection=collection)

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        collection = _safe_collection_name(collection)
        # Strip keys the collection schema does not declare. Pre-Issue#44
        # collections (Milvus 2.5 servers without AddCollectionField RPC)
        # do not have source / source_id columns, so writing them would
        # 422 the whole batch.
        schema_fields = await self._collection_field_names(collection)
        entities: list[dict[str, Any]] = []
        for uid, vec, pay in zip(ids, vectors, payloads, strict=True):
            entity: dict[str, Any] = {
                "id": uid,
                "vector": vec,
                "tenant_id": pay.get("tenant_id", ""),
                "document_id": pay.get("document_id", ""),
                "content": pay.get("content", "")[:65535],
                "chunk_index": pay.get("chunk_index", 0),
                "content_type": pay.get("content_type", ""),
                "language": pay.get("language", ""),
                "source": pay.get("source", ""),
                "source_id": pay.get("source_id", ""),
                "extra": {
                    k: v for k, v in pay.items() if k not in _KNOWN_FIELDS
                },
            }
            if schema_fields:
                entity = {
                    k: v for k, v in entity.items() if k in schema_fields
                }
            entities.append(entity)

        await asyncio.to_thread(
            self._client.upsert,
            collection_name=collection,
            data=entities,
        )
        logger.info("milvus.upsert", collection=collection, count=len(entities))

    async def delete(
        self,
        collection: str,
        filters: dict[str, Any],
        *,
        raise_on_error: bool = False,
    ) -> None:
        """Filter-based delete。

        ``raise_on_error=False``（預設）保持原本 swallow-and-log 行為，避免
        既有 in-band caller (DeleteDocument / DeleteChunk) 因 Milvus 短暫
        不可用就讓 PG 也卡住。``raise_on_error=True`` 給 outbox drain
        handler 用，讓失敗能進 retry/DLQ。
        """
        collection = _safe_collection_name(collection)
        try:
            expr = _build_filter_expr(filters)
            await asyncio.to_thread(
                self._client.delete,
                collection_name=collection,
                filter=expr,
            )
            logger.info("milvus.delete", collection=collection, filters=filters)
        except Exception:
            logger.warning(
                "milvus.delete.skipped",
                collection=collection,
                filters=filters,
                exc_info=True,
            )
            if raise_on_error:
                raise

    async def drop_collection(self, collection: str) -> None:
        """整個 collection 刪除（DeleteKB outbox handler 用）。

        Drop 已不存在的 collection 是 no-op（Milvus client 行為），符合
        outbox handler 的 idempotent 要求。``raise_on_error`` 永遠隱含
        True — drop_collection 失敗代表 Milvus 不可用，應進 retry 而非吞掉。
        """
        collection = _safe_collection_name(collection)
        try:
            has_collection = await asyncio.to_thread(
                self._client.has_collection, collection_name=collection
            )
            if not has_collection:
                logger.info(
                    "milvus.drop_collection.noop",
                    collection=collection,
                )
                return
            await asyncio.to_thread(
                self._client.drop_collection, collection_name=collection
            )
            logger.info("milvus.drop_collection", collection=collection)
        except Exception:
            logger.warning(
                "milvus.drop_collection.failed",
                collection=collection,
                exc_info=True,
            )
            raise

    async def fetch_vectors(
        self,
        collection: str,
        ids: list[str],
    ) -> list[tuple[str, list[float], dict[str, Any]]]:
        """Fetch vectors + payloads by IDs from Milvus."""
        collection = _safe_collection_name(collection)
        if not ids:
            return []
        try:
            results = await asyncio.to_thread(
                self._client.get,
                collection_name=collection,
                ids=ids,
                output_fields=["vector", "content", "tenant_id", "document_id"],
            )
            out: list[tuple[str, list[float], dict[str, Any]]] = []
            for r in results:
                rid = r.get("id", "")
                vec = r.get("vector", [])
                payload = {k: v for k, v in r.items() if k not in ("id", "vector")}
                out.append((rid, vec, payload))
            return out
        except Exception:
            logger.warning("milvus.fetch_vectors.failed", collection=collection, exc_info=True)
            return []

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 5,
        score_threshold: float = 0.3,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        collection = _safe_collection_name(collection)
        filter_expr = _build_filter_expr(filters) if filters else ""

        t0 = time.perf_counter()
        # Restrict output_fields to those the collection actually has —
        # otherwise pre-Issue#44 collections raise on missing source / source_id.
        all_output = ["tenant_id", "document_id", "content",
                      "chunk_index", "content_type", "language",
                      "source", "source_id", "extra"]
        schema_fields = await self._collection_field_names(collection)
        if schema_fields:
            output_fields = [f for f in all_output if f in schema_fields]
        else:
            output_fields = all_output

        results = await asyncio.to_thread(
            self._client.search,
            collection_name=collection,
            data=[query_vector],
            limit=limit,
            output_fields=output_fields,
            filter=filter_expr or None,
        )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        # Milvus returns list of list (one per query vector)
        hits = results[0] if results else []

        # Convert Milvus distance to similarity score
        # Milvus COSINE: distance in [0, 2], similarity = 1 - distance/2
        # But pymilvus MilvusClient.search returns 'distance' which for COSINE
        # is already the similarity score (1 - cosine_distance) in [0, 1]
        search_results: list[SearchResult] = []
        for hit in hits:
            score = float(hit.get("distance", 0))
            if score < score_threshold:
                continue

            entity = hit.get("entity", {})
            payload: dict[str, Any] = {
                "tenant_id": entity.get("tenant_id", ""),
                "document_id": entity.get("document_id", ""),
                "content": entity.get("content", ""),
                "chunk_index": entity.get("chunk_index", 0),
                "content_type": entity.get("content_type", ""),
                "language": entity.get("language", ""),
                "source": entity.get("source", ""),
                "source_id": entity.get("source_id", ""),
            }
            extra = entity.get("extra", {})
            if extra:
                payload.update(extra)

            search_results.append(
                SearchResult(
                    id=str(hit.get("id", "")),
                    score=score,
                    payload=payload,
                )
            )

        logger.info(
            "milvus.search",
            collection=collection,
            result_count=len(search_results),
            latency_ms=elapsed_ms,
        )
        return search_results

    # ──────────────────────────────────────────────────────────────────
    # S-Gov.6b: Conversation Summary collection methods
    # ──────────────────────────────────────────────────────────────────
    #
    # 設計：reuse 既有 schema（id / vector / tenant_id / document_id / content / extra）
    # mapping：
    #   id          → conversation_id（PK，upsert 同 conv_id 自動覆蓋）
    #   tenant_id   → conv.tenant_id（filter 用）
    #   document_id → bot_id（語意 reuse — 用 bot_id 過濾同 bot 的對話）
    #   content     → summary text（搜尋結果回顯）
    #   extra       → 其他 metadata（first_message_at / message_count / summary_at）

    CONV_SUMMARIES_COLLECTION = "conv_summaries"
    CONV_SUMMARY_VECTOR_DIM = 3072  # text-embedding-3-large

    async def ensure_conv_summaries_collection(self) -> None:
        """確保 conv_summaries collection 存在（vector dim=3072）。"""
        await self.ensure_collection(
            self.CONV_SUMMARIES_COLLECTION,
            self.CONV_SUMMARY_VECTOR_DIM,
        )

    async def upsert_conv_summary(
        self,
        *,
        conversation_id: str,
        embedding: list[float],
        tenant_id: str,
        bot_id: str | None,
        summary: str,
        first_message_at: str | None = None,
        message_count: int = 0,
        summary_at: str | None = None,
    ) -> None:
        """Upsert 單一對話 summary vector（同 conv_id 自動覆蓋）。"""
        await self.ensure_conv_summaries_collection()
        payload: dict[str, Any] = {
            "tenant_id": tenant_id,
            "document_id": bot_id or "",  # reuse 為 bot_id filter
            "content": summary,
            "first_message_at": first_message_at or "",
            "message_count": message_count,
            "summary_at": summary_at or "",
        }
        await self.upsert(
            collection=self.CONV_SUMMARIES_COLLECTION,
            ids=[conversation_id],
            vectors=[embedding],
            payloads=[payload],
        )

    async def search_conv_summaries(
        self,
        *,
        query_vector: list[float],
        tenant_id: str | None = None,
        bot_id: str | None = None,
        limit: int = 20,
        score_threshold: float = 0.3,
    ) -> list[SearchResult]:
        """Semantic search 對話摘要。回傳 SearchResult 含 conversation_id (id)
        + summary (content) + payload metadata。
        """
        filters: dict[str, Any] = {}
        if tenant_id is not None:
            filters["tenant_id"] = tenant_id
        if bot_id is not None:
            filters["document_id"] = bot_id  # reuse semantic
        return await self.search(
            collection=self.CONV_SUMMARIES_COLLECTION,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            filters=filters or None,
        )

    # --- S-KB-Studio.1 新增：Admin Dashboard / 單 chunk re-embed ---

    async def list_collections(self) -> list[dict[str, Any]]:
        """列出所有 collection + row count。"""
        names = await asyncio.to_thread(self._client.list_collections)
        out: list[dict[str, Any]] = []
        for name in names:
            try:
                stats = await asyncio.to_thread(
                    self._client.get_collection_stats, collection_name=name
                )
                row_count = int(stats.get("row_count", 0))
            except Exception:
                row_count = 0
            out.append({"name": name, "row_count": row_count})
        return out

    async def get_collection_stats(
        self, collection: str
    ) -> dict[str, Any]:
        """回傳 collection 詳細：row_count, loaded, indexes, vector_dim。"""
        collection = _safe_collection_name(collection)
        try:
            stats = await asyncio.to_thread(
                self._client.get_collection_stats, collection_name=collection
            )
            row_count = int(stats.get("row_count", 0))
        except Exception as e:
            logger.warning(
                "milvus.stats.failed", collection=collection, error=str(e)
            )
            row_count = 0

        # loaded 判斷：嘗試 describe collection load state
        try:
            load_state = await asyncio.to_thread(
                self._client.get_load_state, collection_name=collection
            )
            loaded = bool(load_state) and str(load_state).lower().find("loaded") != -1
        except Exception:
            loaded = True  # 無法判斷，預設 True

        # indexes：掃描三個已知 scalar field + vector
        indexes: list[dict[str, Any]] = []
        for field in ("tenant_id", "document_id", "vector"):
            try:
                info = await asyncio.to_thread(
                    self._client.describe_index,
                    collection_name=collection,
                    index_name=field,
                )
                if isinstance(info, list) and info:
                    info = info[0]
                idx_type = (
                    info.get("index_type") if isinstance(info, dict) else None
                )
                indexes.append(
                    {
                        "field": field,
                        "index_type": idx_type or "(empty)",
                    }
                )
            except Exception:
                indexes.append({"field": field, "index_type": "none"})

        return {
            "row_count": row_count,
            "loaded": loaded,
            "indexes": indexes,
        }

    async def upsert_single(
        self,
        collection: str,
        id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """單筆 upsert；payload 必含 tenant_id（caller 層保證）。"""
        if "tenant_id" not in payload:
            raise ValueError(
                "upsert_single payload must include tenant_id "
                "(safety boundary for multi-tenant isolation)"
            )
        collection = _safe_collection_name(collection)
        data = [{"id": id, "vector": vector, **payload}]
        await asyncio.to_thread(
            self._client.upsert, collection_name=collection, data=data
        )

    async def update_payload(
        self,
        collection: str,
        id: str,
        payload_diff: dict[str, Any],
    ) -> None:
        """改 payload 不改向量。Milvus 需先 fetch 再 upsert。"""
        collection = _safe_collection_name(collection)
        existing = await self.fetch_vectors(collection, [id])
        if not existing:
            logger.warning(
                "milvus.update_payload.not_found",
                collection=collection, id=id,
            )
            return
        _, vector, old_payload = existing[0]
        new_payload = {**old_payload, **payload_diff}
        await self.upsert_single(
            collection=collection, id=id, vector=vector, payload=new_payload
        )

    async def count_by_filter(
        self,
        collection: str,
        filters: dict[str, Any],
    ) -> int:
        """回傳符合 filter 的 row 數。"""
        collection = _safe_collection_name(collection)
        expr = _build_filter_expr(filters)
        try:
            res = await asyncio.to_thread(
                self._client.query,
                collection_name=collection,
                filter=expr,
                output_fields=["id"],
                limit=16384,
            )
            return len(res) if res else 0
        except Exception as e:
            logger.warning(
                "milvus.count.failed",
                collection=collection, filter=expr, error=str(e),
            )
            return 0

    async def rebuild_scalar_indexes(
        self, collection: str
    ) -> dict[str, Any]:
        """對舊 collection 重建 tenant_id / document_id 的 INVERTED index。"""
        collection = _safe_collection_name(collection)
        result: dict[str, Any] = {"fields": {}}
        try:
            await asyncio.to_thread(
                self._client.release_collection, collection_name=collection
            )
        except Exception:
            pass

        for field in ("tenant_id", "document_id"):
            try:
                await asyncio.to_thread(
                    self._client.drop_index,
                    collection_name=collection,
                    index_name=field,
                )
            except Exception:
                pass
            params = self._client.prepare_index_params()
            params.add_index(field_name=field, index_type="INVERTED")
            try:
                await asyncio.to_thread(
                    self._client.create_index,
                    collection_name=collection,
                    index_params=params,
                )
                result["fields"][field] = "rebuilt"
            except Exception as e:
                result["fields"][field] = f"failed: {e}"

        try:
            await asyncio.to_thread(
                self._client.load_collection, collection_name=collection
            )
            result["loaded"] = True
        except Exception as e:
            result["loaded"] = f"failed: {e}"
        return result
