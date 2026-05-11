"""Unit tests for sliced OCR helper (切片 + 多 tile OCR + 合併)。"""

from __future__ import annotations

import asyncio
import io

import pytest
from PIL import Image

from src.infrastructure.file_parser.sliced_ocr_helper import (
    merge_tile_texts,
    ocr_image_sliced,
    parse_grid_spec,
    slice_image_bytes,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_test_image_bytes(w: int = 800, h: int = 1200) -> bytes:
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── parse_grid_spec ──


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("", None),
        ("2x3", (2, 3)),
        ("3x2", (3, 2)),
        ("2X3", (2, 3)),  # case-insensitive
        ("invalid", None),
        ("2x", None),
        ("0x3", None),  # 0 列不合法
        ("6x6", None),  # 超過 5x5 安全上限
        ("a x b", None),
    ],
)
def test_parse_grid_spec(spec: str, expected: tuple[int, int] | None):
    assert parse_grid_spec(spec) == expected


# ── slice_image_bytes ──


def test_slice_image_bytes_2x3_returns_6_tiles():
    img_bytes = _make_test_image_bytes(800, 1200)
    tiles = slice_image_bytes(img_bytes, rows=2, cols=3)
    assert len(tiles) == 6


def test_slice_image_bytes_3x2_returns_6_tiles():
    img_bytes = _make_test_image_bytes(800, 1200)
    tiles = slice_image_bytes(img_bytes, rows=3, cols=2)
    assert len(tiles) == 6


def test_slice_image_bytes_tiles_are_valid_png():
    img_bytes = _make_test_image_bytes(400, 600)
    tiles = slice_image_bytes(img_bytes, rows=2, cols=2)
    for tile in tiles:
        img = Image.open(io.BytesIO(tile))
        # 每個 tile 應為合法 PNG，且尺寸 > 0
        assert img.size[0] > 0 and img.size[1] > 0


def test_slice_image_bytes_with_overlap_tiles_overlap_each_other():
    """Overlap：相鄰 tile 寬度總和 > 整圖寬度（因 overlap 像素重複）。"""
    img_bytes = _make_test_image_bytes(800, 1200)
    tiles = slice_image_bytes(img_bytes, rows=1, cols=2)
    tile1 = Image.open(io.BytesIO(tiles[0]))
    tile2 = Image.open(io.BytesIO(tiles[1]))
    # 1x2 切：兩 tile 寬度總和應 > 800 (因為 overlap)
    assert tile1.width + tile2.width > 800


# ── merge_tile_texts ──


def test_merge_tile_texts_joins_with_double_newline():
    texts = ["商品 A", "商品 B", "商品 C"]
    merged = merge_tile_texts(texts)
    assert "商品 A" in merged
    assert "商品 B" in merged
    assert "商品 C" in merged


def test_merge_tile_texts_skips_empty():
    texts = ["A", "", "  ", "B"]
    merged = merge_tile_texts(texts)
    assert merged == "A\n\nB"


# ── ocr_image_sliced ──


def test_ocr_image_sliced_with_empty_grid_calls_callback_once():
    """grid="" → 直接整圖 OCR，不切片。"""
    img_bytes = _make_test_image_bytes()
    call_count = 0

    async def cb(b: bytes) -> str:
        nonlocal call_count
        call_count += 1
        return "single text"

    result = _run(ocr_image_sliced(img_bytes, "", cb))
    assert call_count == 1
    assert result == "single text"


def test_ocr_image_sliced_2x3_calls_callback_6_times():
    """grid="2x3" → 切 6 tile，callback 被呼叫 6 次。"""
    img_bytes = _make_test_image_bytes()
    call_count = 0

    async def cb(b: bytes) -> str:
        nonlocal call_count
        call_count += 1
        return f"tile {call_count}"

    result = _run(ocr_image_sliced(img_bytes, "2x3", cb))
    assert call_count == 6
    # 合併結果包含所有 tile 內容
    for i in range(1, 7):
        assert f"tile {i}" in result


def test_ocr_image_sliced_invalid_grid_falls_back_to_single_call():
    """invalid grid spec → fallback 整圖 OCR（不 crash）。"""
    img_bytes = _make_test_image_bytes()
    call_count = 0

    async def cb(b: bytes) -> str:
        nonlocal call_count
        call_count += 1
        return "fallback"

    result = _run(ocr_image_sliced(img_bytes, "invalid", cb))
    assert call_count == 1
    assert result == "fallback"


def test_ocr_image_sliced_runs_tiles_in_parallel():
    """多 tile OCR 應 asyncio.gather 並發，不應序列化。"""
    img_bytes = _make_test_image_bytes()
    start_times: list[float] = []
    import time

    async def cb(b: bytes) -> str:
        start_times.append(time.perf_counter())
        await asyncio.sleep(0.05)
        return "ok"

    t0 = time.perf_counter()
    _run(ocr_image_sliced(img_bytes, "2x3", cb))
    total = time.perf_counter() - t0
    # 序列 6 tile = 0.3s+；並發應 < 0.2s
    assert total < 0.2, f"並發未生效 — 總耗時 {total:.3f}s 太長"
