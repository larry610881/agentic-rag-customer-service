"""Extract PDF pages as PNG images using PyMuPDF."""

from __future__ import annotations

from collections.abc import Generator


def extract_pages_as_images(raw_bytes: bytes, dpi: int = 200) -> list[bytes]:
    """Return a list of PNG bytes, one per PDF page."""
    return list(iter_pages_as_images(raw_bytes, dpi))


def iter_pages_as_images(raw_bytes: bytes, dpi: int = 200) -> Generator[bytes, None, None]:
    """Yield PNG bytes one page at a time (memory efficient)."""
    import fitz

    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        for page in doc:
            pix = page.get_pixmap(matrix=mat)
            png = pix.tobytes("png")
            pix = None  # Free pixmap memory immediately
            yield png
    finally:
        doc.close()


def count_pages(raw_bytes: bytes) -> int:
    """Count PDF pages without rendering."""
    import fitz

    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    count = len(doc)
    doc.close()
    return count
