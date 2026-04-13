"""Claude Vision OCR engine using Anthropic Python SDK."""

from __future__ import annotations

import asyncio
import base64

import anthropic

from src.domain.shared.exceptions import OcrProcessingError
from src.infrastructure.file_parser.ocr_engines.base import OcrEngine

_OCR_PROMPT = (
    "Extract all visible text from this page. "
    "Return only the text content in reading order. No commentary."
)


class ClaudeVisionOcrEngine(OcrEngine):
    """OCR engine that uses Claude Vision API for text extraction."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        max_concurrent: int = 5,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def ocr_page(self, image_bytes: bytes) -> str:
        b64 = base64.standard_b64encode(image_bytes).decode()
        try:
            async with self._semaphore:
                message = await self._client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": b64,
                                    },
                                },
                                {"type": "text", "text": _OCR_PROMPT},
                            ],
                        }
                    ],
                )
                return message.content[0].text
        except anthropic.APIError as e:
            raise OcrProcessingError(f"Claude API error: {e}") from e
        except (KeyError, IndexError) as e:
            raise OcrProcessingError(str(e)) from e
