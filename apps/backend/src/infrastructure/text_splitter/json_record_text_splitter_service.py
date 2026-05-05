import json

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.services import TextSplitterService
from src.domain.knowledge.value_objects import ChunkId


def _flatten_nested_records(records: list[dict]) -> list[dict] | None:
    """Flatten nested array-of-objects into flat records.

    Example input:
        [{"category": "FAQ", "items": [{"q": "...", "a": "..."}]}]
    Output:
        [{"category": "FAQ", "q": "...", "a": "..."}, ...]

    Returns None if no nested arrays found (already flat).
    """
    # Find which key contains nested list[dict]
    nested_key = None
    for record in records:
        for k, v in record.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                nested_key = k
                break
        if nested_key:
            break

    if nested_key is None:
        return None  # Already flat

    flat: list[dict] = []
    for record in records:
        children = record.get(nested_key)
        if not isinstance(children, list):
            continue
        # Parent context = all scalar fields (not the nested array)
        parent_ctx = {
            k: v
            for k, v in record.items()
            if k != nested_key and not isinstance(v, (list, dict))
        }
        for child in children:
            if isinstance(child, dict):
                flat.append({**parent_ctx, **child})

    return flat if flat else None


class JsonRecordTextSplitterService(TextSplitterService):
    """Record-based JSON splitter — 1 record = 1 chunk (no merging).

    JSON 結構天然有 record 邊界，每筆 record 通常本身就是語意單位
    （Q&A 一對 / Order 一筆 / Product 一個）。直接以 record 邊界切，
    不看 chunk_size 合併小記錄 — 因為合併會稀釋 embedding 信號（多
    個語意主題擠在一個 chunk，搜尋相似度被無關 record 的詞稀釋）。

    Trade-off：產出的 chunks 可能比較碎（小 record 一個 chunk 才幾十
    字），但 embedding 精準度顯著提升。對 FAQ / Q&A / 商品目錄等場景
    這是正確的 semantic boundary。

    超長 record（例如單筆 5K+ chars）目前仍當作一個 chunk —
    text-embedding-3-large 上限 8K tokens，實際 FAQ / Q&A 場景幾乎
    不會超過。若未來真的有過長 record，再加 fallback sub-split。

    ``chunk_size`` 參數保留是為了 backward-compat container wiring，
    但不再用於 record merging 決策（記為僅作 future use 例如 sub-split
    超長 record 的閾值，目前未啟用）。
    """

    def __init__(
        self,
        chunk_size: int = 500,
        fallback: TextSplitterService | None = None,
    ) -> None:
        self._chunk_size = chunk_size
        self._fallback = fallback

    def split(
        self,
        text: str,
        document_id: str,
        tenant_id: str,
        content_type: str = "",
    ) -> list[Chunk]:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return self._do_fallback(text, document_id, tenant_id, content_type)

        records = self._extract_records(data)
        if records is None:
            return self._do_fallback(text, document_id, tenant_id, content_type)

        chunks: list[Chunk] = []
        for i, record in enumerate(records):
            record_text = self._format_record(record)
            chunks.append(
                self._make_chunk(
                    record_text,
                    document_id,
                    tenant_id,
                    content_type,
                    chunk_index=i,
                    record_start=i,
                    record_end=i,
                )
            )
        return chunks

    @staticmethod
    def _extract_records(data: object) -> list[dict] | None:
        """Extract a flat list of record dicts from parsed JSON.

        Supports:
        1. [{...}, {...}]  — flat array of objects
        2. {"key": [{...}]}  — dict with one array value
        3. [{"category": "...", "items": [{...}]}]  — nested: auto-flatten
           with parent scalar fields injected into each child record
        """
        if isinstance(data, list) and data and isinstance(data[0], dict):
            # Check if records contain nested arrays → flatten
            flattened = _flatten_nested_records(data)
            if flattened is not None:
                return flattened
            return data
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    flattened = _flatten_nested_records(v)
                    if flattened is not None:
                        return flattened
                    return v
        return None

    @staticmethod
    def _format_record(record: dict) -> str:
        """Format a single JSON object as readable key: value lines."""
        lines: list[str] = []
        for key, value in record.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _make_chunk(
        content: str,
        document_id: str,
        tenant_id: str,
        content_type: str,
        chunk_index: int,
        record_start: int,
        record_end: int,
    ) -> Chunk:
        return Chunk(
            id=ChunkId(),
            document_id=document_id,
            tenant_id=tenant_id,
            content=content,
            chunk_index=chunk_index,
            metadata={
                "document_id": document_id,
                "tenant_id": tenant_id,
                "content_type": content_type or "application/json",
                "record_start": record_start,
                "record_end": record_end,
            },
        )

    def _do_fallback(
        self,
        text: str,
        document_id: str,
        tenant_id: str,
        content_type: str,
    ) -> list[Chunk]:
        if self._fallback:
            return self._fallback.split(text, document_id, tenant_id, content_type)
        return []
