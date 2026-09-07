"""OCR 引擎共用的影像前處理（Issue #78 自 claude_vision_ocr 抽出）。"""

from __future__ import annotations

import io

_MAX_IMAGE_BYTES = 3_500_000  # ~3.5MB raw → ~4.7MB after base64 (stays under Claude's 5MB limit)


def detect_mime(image_bytes: bytes) -> str:
    """依 magic bytes 判斷 png / jpeg / webp；未知一律當 png。"""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _compress_image(image_bytes: bytes) -> tuple[bytes, str]:
    """Compress image to fit within Claude API size limit.

    Returns (image_bytes, media_type).
    """
    if len(image_bytes) <= _MAX_IMAGE_BYTES:
        return image_bytes, detect_mime(image_bytes)

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
