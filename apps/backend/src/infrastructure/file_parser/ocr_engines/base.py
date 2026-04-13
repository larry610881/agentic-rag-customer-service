from abc import ABC, abstractmethod


class OcrEngine(ABC):
    """Abstract base class for OCR engines that extract text from images."""

    @abstractmethod
    async def ocr_page(self, image_bytes: bytes, prompt: str | None = None) -> str:
        """Extract text from a single page image (PNG bytes)."""
        ...
