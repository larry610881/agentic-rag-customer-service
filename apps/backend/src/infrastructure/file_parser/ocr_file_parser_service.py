"""OCR-based file parser that routes PDF through OCR engines.

Issue #78：引擎依 ``provider:model`` spec 動態選擇（:class:`DynamicOcrEngineFactory`），
本服務同時實作 :class:`OcrEngineSelector` port 供 use case 依
``KB.ocr_model → 租戶 default_ocr_model → 環境預設`` 取得引擎。
每次解析的用量累加到 caller 傳入的 :class:`OcrUsageTally`（每份文件一份），
``last_*`` 屬性僅為向後相容而保留（反映最近一次呼叫）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from src.domain.knowledge.services import FileParserService, OcrEngineSelector
from src.domain.knowledge.value_objects import OcrUsageTally
from src.infrastructure.file_parser.default_file_parser_service import (
    DefaultFileParserService,
)
from src.infrastructure.file_parser.ocr_engines.base import OcrEngine
from src.infrastructure.file_parser.ocr_engines.factory import (
    DynamicOcrEngineFactory,
)
from src.infrastructure.file_parser.ocr_engines.prompts import OCR_PROMPTS
from src.infrastructure.file_parser.pdf_page_extractor import (
    extract_pages_as_images,
)

# Callback type: (completed_pages, total_pages) -> Awaitable
ProgressCallback = Callable[[int, int], Awaitable[None]]


class OcrFileParserService(FileParserService, OcrEngineSelector):
    """FileParserService that routes PDF to OCR, delegates others to default."""

    def __init__(
        self,
        ocr_engine: OcrEngine | None = None,
        engine_factory: DynamicOcrEngineFactory | None = None,
    ) -> None:
        if ocr_engine is None and engine_factory is None:
            raise ValueError("OcrFileParserService needs ocr_engine or engine_factory")
        self._factory = engine_factory
        # 預設引擎：明確注入者優先，否則由 factory 依環境預設 spec 建立
        self._ocr: OcrEngine = (
            ocr_engine
            if ocr_engine is not None
            else engine_factory.engine_for(engine_factory.default_spec)  # type: ignore[union-attr]
        )
        self._default = DefaultFileParserService()
        # Expose last parse usage for callers to record (backward compat)
        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0
        self.last_model: str = ""

    # ── OcrEngineSelector ──

    def resolve_ocr_spec(
        self, kb_ocr_model: str, tenant_default_ocr_model: str
    ) -> str:
        if self._factory is not None:
            return self._factory.resolve_spec(kb_ocr_model, tenant_default_ocr_model)
        return getattr(self._ocr, "model_spec", "") or ""

    def ocr_engine_for(self, spec: str) -> OcrEngine:
        if self._factory is not None:
            return self._factory.engine_for(spec)
        return self._ocr

    # ── FileParserService ──

    def supported_types(self) -> set[str]:
        return self._default.supported_types()

    def parse(
        self, raw_bytes: bytes, content_type: str, ocr_mode: str = "general"
    ) -> str:
        self.last_input_tokens = 0
        self.last_output_tokens = 0

        if content_type != "application/pdf":
            return self._default.parse(raw_bytes, content_type)

        # general mode: use pypdf text extraction (no LLM needed)
        if ocr_mode == "general":
            return self._default.parse(raw_bytes, content_type)

        # catalog/ocr mode: use vision OCR
        page_images = extract_pages_as_images(raw_bytes)
        if not page_images:
            return ""

        prompt = OCR_PROMPTS.get(ocr_mode, OCR_PROMPTS["general"])
        usage = OcrUsageTally()
        result = asyncio.run(self._ocr_all_pages(page_images, prompt, usage))
        self._publish_usage(usage, self._ocr)
        return result

    async def parse_pdf_async(
        self,
        raw_bytes: bytes,
        ocr_mode: str = "general",
        on_progress: ProgressCallback | None = None,
        max_pages: int | None = None,
        *,
        engine: OcrEngine | None = None,
        usage: OcrUsageTally | None = None,
    ) -> str:
        """Async PDF parsing with per-page progress callback.

        ``ocr_mode``：
        - ``"general"``：pypdf 文字抽取（無 LLM）
        - ``"catalog"``：單一 _CATALOG_PROMPT 走全部頁
        - ``"auto"``：每頁先偵測類型（catalog/promotion/mixed/cover），
          再 dispatch 至對應 prompt — 解決混雜 DM（部分商品 + 部分信用卡 /
          會員活動 / 服務介紹頁）OCR 失敗的問題

        ``engine``：本次使用的 OCR 引擎（未給 → 預設引擎）；
        ``usage``：caller 持有的用量累計（未給 → 內部建立、僅反映到 last_*）。
        """
        self.last_input_tokens = 0
        self.last_output_tokens = 0

        # general mode: use pypdf text extraction (no LLM needed)
        if ocr_mode == "general":
            content = await asyncio.to_thread(
                self._default.parse, raw_bytes, "application/pdf"
            )
            if on_progress:
                await on_progress(1, 1)
            return content

        # catalog / auto mode: 走 vision OCR
        page_images = extract_pages_as_images(raw_bytes)
        if not page_images:
            return ""

        if max_pages:
            page_images = page_images[:max_pages]

        ocr = engine if engine is not None else self._ocr
        tally = usage if usage is not None else OcrUsageTally()
        total = len(page_images)

        page_texts: list[str] = []
        # Process in batches of concurrent size (semaphore handles concurrency)
        batch_size = 5

        if ocr_mode == "auto":
            # 每頁 classify → dispatch
            for i in range(0, total, batch_size):
                batch = page_images[i : i + batch_size]
                pairs = await asyncio.gather(
                    *[ocr.ocr_page_auto_dispatch(img, usage=tally) for img in batch]
                )
                page_texts.extend(text for _page_type, text in pairs)
                if on_progress:
                    await on_progress(len(page_texts), total)
        else:
            # 既有 catalog 單一 prompt 路徑
            prompt = OCR_PROMPTS.get(ocr_mode, OCR_PROMPTS["general"])
            for i in range(0, total, batch_size):
                batch = page_images[i : i + batch_size]
                texts = await asyncio.gather(
                    *[ocr.ocr_page(img, prompt, usage=tally) for img in batch]
                )
                page_texts.extend(texts)
                if on_progress:
                    await on_progress(len(page_texts), total)

        self._publish_usage(tally, ocr)
        return "\f".join(page_texts)

    async def _ocr_all_pages(
        self, page_images: list[bytes], prompt: str, usage: OcrUsageTally
    ) -> str:
        tasks = [self._ocr.ocr_page(img, prompt, usage=usage) for img in page_images]
        page_texts = await asyncio.gather(*tasks)
        return "\f".join(page_texts)

    def _publish_usage(self, usage: OcrUsageTally, engine: OcrEngine) -> None:
        """把本次用量反映到 last_*（舊 caller 相容）。"""
        self.last_input_tokens = usage.input_tokens
        self.last_output_tokens = usage.output_tokens
        spec = getattr(engine, "model_spec", "")
        model = getattr(engine, "_model", "")
        self.last_model = (
            usage.model
            or (spec if isinstance(spec, str) else "")
            or (model if isinstance(model, str) else "")
            or "unknown"
        )
