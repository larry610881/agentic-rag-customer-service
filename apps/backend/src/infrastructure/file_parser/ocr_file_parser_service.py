"""OCR-based file parser that routes PDF through OCR engines."""

from __future__ import annotations

import asyncio

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
        # Reset engine counters before batch
        self._ocr.last_input_tokens = 0
        self._ocr.last_output_tokens = 0
        result = asyncio.run(self._ocr_all_pages(page_images, prompt))
        # Copy accumulated usage
        self.last_input_tokens = self._ocr.last_input_tokens
        self.last_output_tokens = self._ocr.last_output_tokens
        self.last_model = getattr(self._ocr, "_model", "unknown")
        return result

    async def _ocr_all_pages(self, page_images: list[bytes], prompt: str) -> str:
        tasks = [self._ocr.ocr_page(img, prompt) for img in page_images]
        page_texts = await asyncio.gather(*tasks)
        return "\f".join(page_texts)
