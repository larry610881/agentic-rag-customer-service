"""Separator-Based Splitter — 按 === 分隔符切 DM 商品目錄。

OCR `_CATALOG_PROMPT` 已輸出每個商品為獨立 `===\n商品：X\n===` block，
頁面 metadata 寫成 `【商家】X` / `【頁面分類】Y` / `【頁面級促銷說明】Z`。

本 splitter：
- 1 商品 block = 1 chunk（不依字數合併，避免主題稀釋）
- 頁面 `【...】` markers + `【頁面級促銷說明】` 區塊 deterministic 抽進
  每個 chunk 的 ``context_text`` 欄位 → embed 時自動 prepend
  （process_document_use_case.py 已有 ``context_text + content`` 組合邏輯）
- Sniff 失敗時 fallback 到 recursive splitter（safety net，避免整批 chunks 變空）

設計：
- ``LLMChunkContextService`` 跟 splitter 寫入的 ``context_text`` 不衝突 —
  Application 層加 guard：若 chunk.context_text 已有值，跳過 LLM 呼叫
  （省成本 + 保留精準頁面 metadata）
- 不改 OCR prompt（page_number 已在 ``Document.page_number`` 欄位，
  retrieval 時 trace 額外帶出，無需重 OCR）
"""

import re

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.services import TextSplitterService
from src.domain.knowledge.value_objects import ChunkId

# === 分隔符商品 block：=== \n {內容} \n ===
# non-greedy 匹配 + 行尾 \n 邊界降低跨 block 誤匹配機率
_PRODUCT_BLOCK_RE = re.compile(r"={3,}\s*\n(.*?)\n={3,}", re.DOTALL)

# 頁面 markers：【key】value（value 不含換行與下一個【）
_HEADER_MARKER_RE = re.compile(r"【([^】]+)】([^\n【]*)")

# 頁面級促銷說明（特殊處理 — 內容可能跨多行直到下個【或文末）
_PAGE_LEVEL_PROMO_RE = re.compile(
    r"【頁面級促銷說明】(.*?)(?=【|\Z)", re.DOTALL
)

# Sniff 條件
_BARE_SEPARATOR_RE = re.compile(r"^={3,}\s*$", re.MULTILINE)
_PRODUCT_KEYWORD_RE = re.compile(r"商品[:：]")


class SeparatorTextSplitterService(TextSplitterService):
    """Separator-based splitter for DM 商品目錄."""

    def __init__(self, fallback: TextSplitterService | None = None) -> None:
        self._fallback = fallback

    def split(
        self,
        text: str,
        document_id: str,
        tenant_id: str,
        content_type: str = "",
    ) -> list[Chunk]:
        if not self._is_catalog_format(text):
            return self._fallback_split(text, document_id, tenant_id, content_type)

        page_context = self._compose_page_context(text)
        product_blocks = self._extract_product_blocks(text)

        if not product_blocks:
            # 有 === 但商品 block 全空（OCR 異常）→ fallback
            return self._fallback_split(text, document_id, tenant_id, content_type)

        return [
            Chunk(
                id=ChunkId(),
                document_id=document_id,
                tenant_id=tenant_id,
                content=block.strip(),
                context_text=page_context,
                chunk_index=i,
                metadata={
                    "document_id": document_id,
                    "tenant_id": tenant_id,
                    "content_type": content_type,
                    "splitter": "separator",
                    "product_index": i,
                },
            )
            for i, block in enumerate(product_blocks)
        ]

    def _fallback_split(
        self,
        text: str,
        document_id: str,
        tenant_id: str,
        content_type: str,
    ) -> list[Chunk]:
        if self._fallback is None:
            return []
        return self._fallback.split(text, document_id, tenant_id, content_type)

    def _is_catalog_format(self, text: str) -> bool:
        """Safety net：即使 KB 設 separator，內容不像 catalog 也 fallback。

        要求：
        - ≥ 2 個 === 分隔符（單行）
        - 文中含「商品：」或「商品:」keyword
        """
        separator_count = len(_BARE_SEPARATOR_RE.findall(text))
        return separator_count >= 2 and bool(_PRODUCT_KEYWORD_RE.search(text))

    @staticmethod
    def _extract_product_blocks(text: str) -> list[str]:
        return [b for b in _PRODUCT_BLOCK_RE.findall(text) if b.strip()]

    @staticmethod
    def _compose_page_context(text: str) -> str:
        """組合頁面 metadata 為 context_text 字串。

        包含：
        - 所有 【key】value markers（除「頁面級促銷說明」獨立處理）
        - 【頁面級促銷說明】區塊（可能跨多行）
        """
        parts: list[str] = []
        seen_keys: set[str] = set()

        for key, value in _HEADER_MARKER_RE.findall(text):
            if key == "頁面級促銷說明":
                continue
            value = value.strip()
            if not value:
                continue
            # 同 key 出現多次保留全部（OCR 偶有變體）
            entry = f"{key}：{value}"
            if entry not in seen_keys:
                parts.append(entry)
                seen_keys.add(entry)

        promo_match = _PAGE_LEVEL_PROMO_RE.search(text)
        if promo_match:
            promo_text = promo_match.group(1).strip()
            if promo_text:
                # 壓平多行為單行（避免破壞 embedding 文本連貫性）
                promo_oneline = re.sub(r"\s+", " ", promo_text)
                parts.append(f"頁面級促銷：{promo_oneline}")

        return " | ".join(parts)
