"""Sliced OCR helper — 切大圖為多 tile + 多次 OCR + 合併輸出。

針對 vision model 對 rare brand char（如「薈」「樟腦」「萃」這類訓練分布
稀有的字）字形辨識率有限的問題：把整頁圖切成 N 個 tile，每個 tile 含有
更高比例的目標字像素 → OCR 準度提升。

驗證結論（page 51 + sonnet-4-6 + _OCR_DISCIPLINE prompt）：
- 整頁: 木之**著**樟腦油 (薈→著, 1 字錯)
- 2x3 grid: **木之薈樟腦油** (✅ 完美)
- 3x3 grid: 木之**薔**樟腦油 (太細缺脈絡, 1 字錯)
- 單獨 crop: 木之**薔**樟腦油 (缺多 tile 互驗, 1 字錯)

設計：
- 純函數 helper，不持有狀態
- 輸入 image bytes + grid spec ("2x3"/"3x2") + OCR callback
- 內部做 whitespace-aware 切片（避免切到文字）+ overlap 防邊界字斷裂
- 多 tile 並發 OCR + 合併文字（用 separator 區隔 tile）

合併策略：tile 間用 splitter 看得懂的格式分隔，讓下游 separator splitter
仍能正確識別 === 商品 block（即使商品橫跨兩個 tile，splitter 會在合併文本
中找到完整 === block）。
"""

from __future__ import annotations

import asyncio
import io
from typing import Awaitable, Callable

WHITE_THRESHOLD = 235
SEARCH_WINDOW = 100  # 切點在理想位置 ± 此範圍找最白邊
# overlap 增加到 80 (原 40)：減少商品 card 跨 tile 邊界 → 降低「半個商品」
# 觸發 LLM 用 [模糊:???] 填欄位的副作用。
# 代價：tile 之間重疊更多 → 同商品可能在 2 tile 都出現 → 但有 _SLICE_AWARE_PREFIX
# 告訴 LLM「半個的省略」，所以 dedup 自動處理。
OVERLAP_PX = 80

OcrCallback = Callable[[bytes], Awaitable[str]]
"""Callable: (image_bytes) -> Awaitable[ocr_text]."""


def parse_grid_spec(spec: str) -> tuple[int, int] | None:
    """Parse "RxC" → (rows, cols) or None for "" (no slicing).

    >>> parse_grid_spec("")
    None  # 不切片，跳過
    >>> parse_grid_spec("2x3")
    (2, 3)
    >>> parse_grid_spec("invalid")
    None  # 格式錯誤視為不啟用
    """
    if not spec:
        return None
    parts = spec.lower().split("x")
    if len(parts) != 2:
        return None
    try:
        r, c = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if r < 1 or c < 1 or r > 5 or c > 5:
        return None  # 安全上限 5x5
    return (r, c)


def _find_split_points(
    arr, axis_size: int, n_splits: int, density
) -> list[int]:
    """在密度低（接近白色）處找切點，避免切到文字。

    density: 1D ndarray，每行/列「非白色像素比例」
    """
    import numpy as np

    splits: list[int] = []
    for k in range(1, n_splits + 1):
        ideal = axis_size * k // (n_splits + 1)
        lo = max(0, ideal - SEARCH_WINDOW)
        hi = min(axis_size, ideal + SEARCH_WINDOW)
        local = density[lo:hi]
        if local.size == 0:
            splits.append(ideal)
            continue
        offset = int(np.argmin(local))
        splits.append(lo + offset)
    return splits


def slice_image_bytes(
    image_bytes: bytes, rows: int, cols: int
) -> list[bytes]:
    """Slice image into rows*cols tiles, whitespace-aware + overlap.

    Returns: list of PNG bytes, one per tile.
    """
    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    arr = np.array(img.convert("L"))
    h, w = arr.shape

    row_density = np.mean(arr < WHITE_THRESHOLD, axis=1)
    col_density = np.mean(arr < WHITE_THRESHOLD, axis=0)

    h_splits = _find_split_points(arr, h, rows - 1, row_density)
    v_splits = _find_split_points(arr, w, cols - 1, col_density)
    h_bounds = [0] + h_splits + [h]
    v_bounds = [0] + v_splits + [w]

    tiles: list[bytes] = []
    for r in range(rows):
        for c in range(cols):
            top = max(0, h_bounds[r] - OVERLAP_PX)
            bot = min(h, h_bounds[r + 1] + OVERLAP_PX)
            left = max(0, v_bounds[c] - OVERLAP_PX)
            right = min(w, v_bounds[c + 1] + OVERLAP_PX)
            tile = img.crop((left, top, right, bot))
            buf = io.BytesIO()
            tile.save(buf, format="PNG")
            tiles.append(buf.getvalue())
    return tiles


def merge_tile_texts(texts: list[str]) -> str:
    """Merge tile OCR results with separator preserving === block structure.

    用空行作 tile 之間的軟分隔。Downstream SeparatorTextSplitterService 找
    === 商品 block 仍會正確，因為 === 不會跨 tile（overlap 確保整個商品
    block 至少完整出現在一個 tile）。
    """
    return "\n\n".join(t for t in texts if t.strip())


async def ocr_image_sliced(
    image_bytes: bytes,
    grid_spec: str,
    ocr_callback: OcrCallback,
) -> str:
    """OCR an image by slicing into tiles + parallel OCR + merge.

    Args:
        image_bytes: source image (PNG/JPEG bytes)
        grid_spec: "2x3" / "3x2" / "" — empty falls back to single OCR call
        ocr_callback: async fn(image_bytes) -> ocr_text，呼叫者注入實際 OCR
                      engine（可帶 prompt / model 等狀態）

    Returns:
        merged OCR text。grid_spec="" 時直接 callback 整圖。
    """
    grid = parse_grid_spec(grid_spec)
    if grid is None:
        return await ocr_callback(image_bytes)

    rows, cols = grid
    tiles = slice_image_bytes(image_bytes, rows, cols)
    texts = await asyncio.gather(*[ocr_callback(t) for t in tiles])
    return merge_tile_texts(list(texts))
