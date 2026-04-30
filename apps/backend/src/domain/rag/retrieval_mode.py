"""RAG retrieval mode enum — Issue #43.

Bot-level retrieval mode 多選：
- ``raw``: 直接用使用者原始 query 做向量檢索
- ``rewrite``: LLM 改寫成更適合向量檢索的 query
- ``hyde``: LLM 先生成假答案，再用假答案做向量檢索

多選會走 multi-query retrieval：N 條 query 並行 embed/search，
結果 union by chunk_id 後再 rerank 取 top_k。

至少要選 1 個（application layer validate；DB 不擋以保留未來擴充）。
"""

from __future__ import annotations

from enum import Enum


class RetrievalMode(str, Enum):
    RAW = "raw"
    REWRITE = "rewrite"
    HYDE = "hyde"

    @classmethod
    def values(cls) -> list[str]:
        return [m.value for m in cls]


def normalize_modes(raw: list[str] | None) -> list[str]:
    """過濾無效值、去重、保留順序；若全部無效 fallback ``[\"raw\"]``。"""
    if not raw:
        return [RetrievalMode.RAW.value]
    valid = set(RetrievalMode.values())
    seen: set[str] = set()
    out: list[str] = []
    for m in raw:
        if m in valid and m not in seen:
            seen.add(m)
            out.append(m)
    return out or [RetrievalMode.RAW.value]


def validate_modes(modes: list[str]) -> None:
    """空 list / 含非法 mode → raise ValueError。"""
    if not modes:
        raise ValueError("rag_retrieval_modes must contain at least 1 mode")
    valid = set(RetrievalMode.values())
    bad = [m for m in modes if m not in valid]
    if bad:
        raise ValueError(
            f"invalid rag_retrieval_modes: {bad}; "
            f"valid options: {sorted(valid)}"
        )
