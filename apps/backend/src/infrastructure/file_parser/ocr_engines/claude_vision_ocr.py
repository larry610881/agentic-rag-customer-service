"""Claude Vision OCR engine using Anthropic Python SDK."""

from __future__ import annotations

import asyncio
import base64
import io

import anthropic

from src.domain.shared.exceptions import OcrProcessingError
from src.infrastructure.file_parser.ocr_engines.base import OcrEngine

_OCR_PROMPT = (
    "Extract all visible text from this page. "
    "Return only the text content in reading order. No commentary."
)

_MAX_IMAGE_BYTES = 3_500_000  # ~3.5MB raw → ~4.7MB after base64 (stays under Claude's 5MB limit)


def _compress_image(image_bytes: bytes) -> tuple[bytes, str]:
    """Compress image to fit within Claude API size limit.

    Returns (image_bytes, media_type).
    """
    if len(image_bytes) <= _MAX_IMAGE_BYTES:
        return image_bytes, "image/png"

    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    if img.mode == "RGBA":
        img = img.convert("RGB")

    for quality in (85, 70, 50, 30):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= _MAX_IMAGE_BYTES:
            return buf.getvalue(), "image/jpeg"

    # Still too large — scale down
    scale = 0.7
    while scale > 0.2:
        new_size = (int(img.width * scale), int(img.height * scale))
        resized = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=60)
        if buf.tell() <= _MAX_IMAGE_BYTES:
            return buf.getvalue(), "image/jpeg"
        scale -= 0.1

    buf = io.BytesIO()
    img.resize((int(img.width * 0.2), int(img.height * 0.2)), Image.LANCZOS).save(
        buf, format="JPEG", quality=40
    )
    return buf.getvalue(), "image/jpeg"


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
        import time

        image_bytes, media_type = _compress_image(image_bytes)
        b64 = base64.standard_b64encode(image_bytes).decode()
        img_kb = len(image_bytes) / 1024
        try:
            async with self._semaphore:
                t0 = time.perf_counter()
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
                                        "media_type": media_type,
                                        "data": b64,
                                    },
                                },
                                {"type": "text", "text": _OCR_PROMPT},
                            ],
                        }
                    ],
                )
                elapsed_ms = round((time.perf_counter() - t0) * 1000)
                usage = message.usage
                from src.infrastructure.logging import get_logger
                logger = get_logger(__name__)
                logger.info(
                    "ocr.page.done",
                    model=self._model,
                    media_type=media_type,
                    image_kb=round(img_kb),
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    elapsed_ms=elapsed_ms,
                )
                return message.content[0].text
        except anthropic.APIError as e:
            raise OcrProcessingError(f"Claude API error: {e}") from e
        except (KeyError, IndexError) as e:
            raise OcrProcessingError(str(e)) from e
