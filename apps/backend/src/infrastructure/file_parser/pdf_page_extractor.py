"""Extract PDF pages as PNG images using PyMuPDF."""

from __future__ import annotations


def extract_pages_as_images(raw_bytes: bytes, dpi: int = 200) -> list[bytes]:
    """Return a list of PNG bytes, one per PDF page."""
    import fitz

    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    pages: list[bytes] = []
    try:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        for page in doc:
            pix = page.get_pixmap(matrix=mat)
            pages.append(pix.tobytes("png"))
    finally:
        doc.close()
    return pages
