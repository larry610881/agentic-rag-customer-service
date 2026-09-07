"""OCR 引擎抽象（Issue #78：帶用量的結果物件 + 共用 auto-dispatch）。

- ``ocr_page_with_usage`` / ``classify_page_type_with_usage`` 為引擎必須實作的
  原語，回傳含 input / output tokens 與實際 ``provider:model`` 的結果。
- ``ocr_page`` / ``classify_page_type`` / ``ocr_page_auto_dispatch`` 為共用的
  便利委派：回傳舊介面的純文字，並把用量累加到 caller 傳入的
  ``OcrUsageTally``（每份文件一份，取代引擎上的共用計數器）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.knowledge.value_objects import OcrUsageTally
from src.infrastructure.file_parser.ocr_engines.prompts import (
    _CATALOG_PROMPT,
    _PAGE_TYPE_PROMPTS,
)


@dataclass(frozen=True)
class OcrPageResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


@dataclass(frozen=True)
class OcrClassifyResult:
    page_type: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class OcrEngine(ABC):
    """Abstract base class for OCR engines that extract text from images."""

    @property
    def model_spec(self) -> str:
        """實際使用的 ``provider:model``；用量記帳的 model 欄位即此值。"""
        return ""

    @abstractmethod
    async def ocr_page_with_usage(
        self, image_bytes: bytes, prompt: str | None = None
    ) -> OcrPageResult:
        """Extract text from a single page image, returning text + usage."""
        ...

    async def classify_page_type_with_usage(
        self, image_bytes: bytes
    ) -> OcrClassifyResult:
        """Detect DM page type (catalog / promotion / mixed / cover) + usage."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support page-type classification"
        )

    # ── 便利委派（舊介面 + 用量累計）──

    async def ocr_page(
        self,
        image_bytes: bytes,
        prompt: str | None = None,
        *,
        usage: OcrUsageTally | None = None,
    ) -> str:
        """Extract text from a single page image (PNG bytes)."""
        result = await self.ocr_page_with_usage(image_bytes, prompt)
        if usage is not None:
            usage.add(result.input_tokens, result.output_tokens, result.model)
        return result.text

    async def classify_page_type(
        self, image_bytes: bytes, *, usage: OcrUsageTally | None = None
    ) -> str:
        result = await self.classify_page_type_with_usage(image_bytes)
        if usage is not None:
            usage.add(result.input_tokens, result.output_tokens, result.model)
        return result.page_type

    async def ocr_page_auto_dispatch(
        self, image_bytes: bytes, *, usage: OcrUsageTally | None = None
    ) -> tuple[str, str]:
        """Classify-then-OCR pipeline for ``ocr_mode="auto"``.

        Returns ``(page_type, ocr_text)`` so caller can record the detected
        type into chunk metadata for future-proofing。
        """
        page_type = await self.classify_page_type(image_bytes, usage=usage)
        prompt = _PAGE_TYPE_PROMPTS.get(page_type, _CATALOG_PROMPT)
        text = await self.ocr_page(image_bytes, prompt=prompt, usage=usage)
        # 在 OCR 輸出開頭注入【偵測類型】tag，便於 chunk 後續 inspection 與
        # baseline diff（不影響 catalog 既有 marker 體系，因 prompt 各自會
        # 產生自己的標題）。
        return page_type, f"【偵測類型】{page_type}\n{text}"
