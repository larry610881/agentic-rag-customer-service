"""Regression — Issue #82：切片 OCR 漏掉跨切片邊界的商品區塊。

DM p13 以 2x3 切片 OCR 時「艾瑪絲 森系列洗髮精系列」（促銷框 + 商品圖 +
文字橫跨切片邊界）在所有 tile 都被「半個商品直接省略」規則丟掉。修法為
混合模式：切片之外再跑一次整頁 OCR，以正規化商品名合併，整頁結果補回
切片漏掉的 block；共用 block 保留切片版（字形較準）；「不詳」的頁面
markers 由整頁補上；兩趟用量皆計入同一份 OcrUsageTally。
"""

from __future__ import annotations

import asyncio
import io

from PIL import Image

from src.application.knowledge._ocr_pipeline import ocr_image
from src.domain.knowledge.value_objects import OcrUsageTally
from src.infrastructure.file_parser.ocr_engines.base import (
    OcrEngine,
    OcrPageResult,
)
from src.infrastructure.file_parser.ocr_engines.prompts import (
    _SLICE_AWARE_PREFIX,
)
from src.infrastructure.text_splitter.separator_text_splitter_service import (
    SeparatorTextSplitterService,
)

_UNKNOWN_MARKERS = (
    "【頁面標題】不詳\n【商家】不詳\n【活動期間】不詳\n"
    "【頁面級促銷說明】不詳\n【頁面分類】商品頁\n"
)

TILE_OUTPUTS = [
    _UNKNOWN_MARKERS + "\n===\n商品：木之薈樟腦油\n品牌：木之薈\n售價：199元/瓶\n===\n",
    _UNKNOWN_MARKERS + "\n===\n商品：好米花蓮玉里有機米\n售價：499元/包\n===\n",
    _UNKNOWN_MARKERS,
    _UNKNOWN_MARKERS,
    _UNKNOWN_MARKERS,
    _UNKNOWN_MARKERS,
]

FULL_PAGE_OUTPUT = """\
【頁面標題】TOP10 熱銷排行榜
【商家】家樂福
【活動期間】2026/04/08～2026/04/21
【頁面級促銷說明】不詳
【頁面分類】商品頁

===
商品：木之著樟腦油
品牌：木之著
售價：199元/瓶
===

===
商品：好米 花蓮玉里有機米
售價：499元/包
===

===
商品：艾瑪絲 森系列洗髮精系列
品牌：AROMASE
促銷：買一送一
===
"""

TILE_TOKENS = (100, 10)
FULL_TOKENS = (300, 30)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _page_png(w: int = 2000, h: int = 3000) -> bytes:
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _FakeHybridEngine(OcrEngine):
    """切片呼叫（prompt 帶切片前綴）依序回 TILE_OUTPUTS；整頁呼叫回整頁輸出。"""

    def __init__(self) -> None:
        self.tile_calls: list[tuple[bytes, str]] = []
        self.full_calls: list[tuple[bytes, str]] = []

    @property
    def model_spec(self) -> str:
        return "google:gemini-3.8-flash"

    async def ocr_page_with_usage(
        self, image_bytes: bytes, prompt: str | None = None
    ) -> OcrPageResult:
        prompt = prompt or ""
        if prompt.startswith(_SLICE_AWARE_PREFIX):
            self.tile_calls.append((image_bytes, prompt))
            text = TILE_OUTPUTS[(len(self.tile_calls) - 1) % len(TILE_OUTPUTS)]
            in_tok, out_tok = TILE_TOKENS
        else:
            self.full_calls.append((image_bytes, prompt))
            text = FULL_PAGE_OUTPUT
            in_tok, out_tok = FULL_TOKENS
        return OcrPageResult(
            text=text, input_tokens=in_tok, output_tokens=out_tok, model=self.model_spec
        )


def _ocr_hybrid() -> tuple[str, _FakeHybridEngine, OcrUsageTally]:
    engine = _FakeHybridEngine()
    usage = OcrUsageTally()
    text = _run(
        ocr_image(
            engine, _page_png(), ocr_mode="catalog", slice_grid="2x3", usage=usage
        )
    )
    return text, engine, usage


def test_hybrid_runs_six_tiles_plus_one_full_page_pass():
    _text, engine, _usage = _ocr_hybrid()
    assert len(engine.tile_calls) == 6
    assert len(engine.full_calls) == 1
    # 整頁 pass 用同一 prompt 家族但不帶切片前綴
    full_prompt = engine.full_calls[0][1]
    assert not full_prompt.startswith(_SLICE_AWARE_PREFIX)
    assert "賣場 DM 結構化提取專家" in full_prompt


def test_hybrid_restores_block_missing_from_all_slices_exactly_once():
    text, _engine, _usage = _ocr_hybrid()
    assert text.count("商品：艾瑪絲 森系列洗髮精系列") == 1
    assert "AROMASE" in text


def test_hybrid_keeps_slice_glyphs_for_shared_blocks():
    text, _engine, _usage = _ocr_hybrid()
    assert "商品：木之薈樟腦油" in text
    assert "木之著" not in text
    assert text.count("好米") == 1


def test_hybrid_fills_unknown_page_markers_from_full_page():
    text, _engine, _usage = _ocr_hybrid()
    assert "【頁面標題】TOP10 熱銷排行榜" in text
    assert "【商家】家樂福" in text
    assert "【活動期間】2026/04/08～2026/04/21" in text
    assert "【商家】不詳" not in text
    assert text.count("【頁面級促銷說明】不詳") == 1


def test_hybrid_usage_sums_both_passes_into_one_tally():
    _text, _engine, usage = _ocr_hybrid()
    assert usage.input_tokens == 6 * TILE_TOKENS[0] + FULL_TOKENS[0]
    assert usage.output_tokens == 6 * TILE_TOKENS[1] + FULL_TOKENS[1]
    assert usage.model == "google:gemini-3.8-flash"


def test_hybrid_full_page_pass_is_downscaled_to_save_tokens():
    _text, engine, _usage = _ocr_hybrid()
    full_img = Image.open(io.BytesIO(engine.full_calls[0][0]))
    assert max(full_img.size) <= 1600
    # 長寬比維持（2000x3000 → 1067x1600）
    assert abs(full_img.width / full_img.height - 2000 / 3000) < 0.01


def test_hybrid_output_is_split_into_one_chunk_per_block():
    text, _engine, _usage = _ocr_hybrid()
    chunks = SeparatorTextSplitterService().split(text, "doc-13", "t-1")
    first_lines = [c.content.splitlines()[0] for c in chunks]
    assert first_lines == [
        "商品：木之薈樟腦油",
        "商品：好米花蓮玉里有機米",
        "商品：艾瑪絲 森系列洗髮精系列",
    ]


def test_hybrid_disabled_by_setting_keeps_slices_only(monkeypatch):
    from src.config import settings

    monkeypatch.setattr(settings, "ocr_hybrid_full_page", False)
    engine = _FakeHybridEngine()
    usage = OcrUsageTally()
    text = _run(
        ocr_image(
            engine, _page_png(), ocr_mode="catalog", slice_grid="2x3", usage=usage
        )
    )
    assert len(engine.tile_calls) == 6
    assert engine.full_calls == []
    assert "艾瑪絲" not in text
    assert usage.input_tokens == 6 * TILE_TOKENS[0]
