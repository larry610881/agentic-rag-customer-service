"""OCR-based file parser that routes PDF through OCR engines."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from src.domain.knowledge.services import FileParserService
from src.infrastructure.file_parser.default_file_parser_service import (
    DefaultFileParserService,
)
from src.infrastructure.file_parser.ocr_engines.claude_vision_ocr import (
    ClaudeVisionOcrEngine,
    OCR_PROMPTS,
)
from src.infrastructure.file_parser.pdf_page_extractor import (
    extract_pages_as_images,
)

# Callback type: (completed_pages, total_pages) -> Awaitable
ProgressCallback = Callable[[int, int], Awaitable[None]]


class OcrFileParserService(FileParserService):
    """FileParserService that routes PDF to OCR, delegates others to default."""

    def __init__(self, ocr_engine: ClaudeVisionOcrEngine) -> None:
        self._ocr = ocr_engine
        self._default = DefaultFileParserService()
        # Expose last parse usage for callers to record
        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0
        self.last_model: str = ""

    def supported_types(self) -> set[str]:
        return self._default.supported_types()

    def parse(
        self, raw_bytes: bytes, content_type: str, ocr_mode: str = "general"
    ) -> str:
        if content_type != "application/pdf":
            self.last_input_tokens = 0
            self.last_output_tokens = 0
            return self._default.parse(raw_bytes, content_type)

        page_images = extract_pages_as_images(raw_bytes)
        if not page_images:
            self.last_input_tokens = 0
            self.last_output_tokens = 0
            return ""

        prompt = OCR_PROMPTS.get(ocr_mode, OCR_PROMPTS["general"])
        self._ocr.last_input_tokens = 0
        self._ocr.last_output_tokens = 0
        result = asyncio.run(self._ocr_all_pages(page_images, prompt))
        self.last_input_tokens = self._ocr.last_input_tokens
        self.last_output_tokens = self._ocr.last_output_tokens
        self.last_model = getattr(self._ocr, "_model", "unknown")
        return result

    async def parse_pdf_async(
        self,
        raw_bytes: bytes,
        ocr_mode: str = "general",
        on_progress: ProgressCallback | None = None,
        max_pages: int | None = None,
    ) -> str:
        """Async PDF parsing with per-page progress callback."""
        page_images = extract_pages_as_images(raw_bytes)
        if not page_images:
            self.last_input_tokens = 0
            self.last_output_tokens = 0
            return ""

        if max_pages:
            page_images = page_images[:max_pages]

        total = len(page_images)
        prompt = OCR_PROMPTS.get(ocr_mode, OCR_PROMPTS["general"])
        self._ocr.last_input_tokens = 0
        self._ocr.last_output_tokens = 0

        page_texts: list[str] = []
        # Process in batches of concurrent size (semaphore handles concurrency)
        batch_size = 5
        for i in range(0, total, batch_size):
            batch = page_images[i : i + batch_size]
            texts = await asyncio.gather(
                *[self._ocr.ocr_page(img, prompt) for img in batch]
            )
            page_texts.extend(texts)
            if on_progress:
                await on_progress(len(page_texts), total)

        self.last_input_tokens = self._ocr.last_input_tokens
        self.last_output_tokens = self._ocr.last_output_tokens
        self.last_model = getattr(self._ocr, "_model", "unknown")
        return "\f".join(page_texts)

    async def _ocr_all_pages(self, page_images: list[bytes], prompt: str) -> str:
        tasks = [self._ocr.ocr_page(img, prompt) for img in page_images]
        page_texts = await asyncio.gather(*tasks)
        return "\f".join(page_texts)
