"""切片 OCR 混合整頁補漏 BDD Step Definitions（Issue #82）"""

from __future__ import annotations

import asyncio
import io

import pytest
from PIL import Image
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.knowledge._ocr_pipeline import ocr_image
from src.config import settings
from src.domain.knowledge.entity import KnowledgeBase
from src.domain.knowledge.value_objects import OcrUsageTally
from src.infrastructure.file_parser.ocr_engines.base import (
    OcrClassifyResult,
    OcrEngine,
    OcrPageResult,
)
from src.infrastructure.file_parser.ocr_engines.prompts import (
    _CATALOG_PROMPT,
    _SLICE_AWARE_PREFIX,
)

scenarios("unit/knowledge/ocr_hybrid_merge.feature")

_MARKERS_UNKNOWN = (
    "【頁面標題】不詳\n【商家】不詳\n【活動期間】不詳\n"
    "【頁面級促銷說明】不詳\n【頁面分類】商品頁\n"
)
_TILE_WITH_BLOCK = _MARKERS_UNKNOWN + "\n===\n商品：木之薈樟腦油\n售價：199元/瓶\n===\n"
_FULL_PAGE = (
    "【頁面標題】TOP10\n【商家】家樂福\n【活動期間】不詳\n"
    "【頁面級促銷說明】不詳\n【頁面分類】商品頁\n\n"
    "===\n商品：木之著樟腦油\n售價：199元/瓶\n===\n\n"
    "===\n商品：艾瑪絲 森系列洗髮精系列\n品牌：AROMASE\n===\n"
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _png() -> bytes:
    img = Image.new("RGB", (800, 1200), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _RecordingEngine(OcrEngine):
    """記錄每次 OCR prompt；切片呼叫只有第一個 tile 帶 block，整頁呼叫帶完整內容。"""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.classify_calls = 0

    @property
    def model_spec(self) -> str:
        return "google:gemini-3.8-flash"

    async def ocr_page_with_usage(
        self, image_bytes: bytes, prompt: str | None = None
    ) -> OcrPageResult:
        prompt = prompt or ""
        self.prompts.append(prompt)
        if prompt.startswith(_SLICE_AWARE_PREFIX):
            n_tiles = sum(1 for p in self.prompts if p.startswith(_SLICE_AWARE_PREFIX))
            text = _TILE_WITH_BLOCK if n_tiles == 1 else _MARKERS_UNKNOWN
        else:
            text = _FULL_PAGE
        return OcrPageResult(text=text, input_tokens=1, output_tokens=1)

    async def classify_page_type_with_usage(
        self, image_bytes: bytes
    ) -> OcrClassifyResult:
        self.classify_calls += 1
        return OcrClassifyResult(page_type="catalog")


@pytest.fixture
def context():
    return {}


# ── Given ──


@given("一個記錄每次呼叫 prompt 的假 OCR 引擎")
def recording_engine(context):
    context["engine"] = _RecordingEngine()


@given(parsers.parse("環境設定 OCR_HYBRID_FULL_PAGE 為 {value}"))
def set_hybrid_setting(context, value, monkeypatch):
    monkeypatch.setattr(settings, "ocr_hybrid_full_page", value.lower() == "true")


@given(
    parsers.re(
        r'知識庫 ocr_mode 為 "(?P<mode>[^"]*)" 且 ocr_slice_grid 為 "(?P<grid>[^"]*)"'
    )
)
def kb_settings(context, mode, grid):
    context["kb"] = KnowledgeBase(ocr_mode=mode, ocr_slice_grid=grid)


# ── When ──


@when("對一張頁面影像執行 OCR")
def run_ocr(context):
    kb: KnowledgeBase = context["kb"]
    context["usage"] = OcrUsageTally()
    context["result"] = _run(
        ocr_image(
            context["engine"],
            _png(),
            ocr_mode=kb.ocr_mode,
            slice_grid=kb.ocr_slice_grid,
            usage=context["usage"],
        )
    )


# ── Then ──


@then(parsers.parse("OCR 引擎應被呼叫 {n:d} 次"))
def engine_call_count(context, n):
    assert len(context["engine"].prompts) == n


@then(parsers.parse("其中 {sliced:d} 次 prompt 帶切片補充規則、{full:d} 次不帶"))
def prompt_kinds(context, sliced, full):
    prompts = context["engine"].prompts
    with_prefix = [p for p in prompts if p.startswith(_SLICE_AWARE_PREFIX)]
    assert len(with_prefix) == sliced
    assert len(prompts) - len(with_prefix) == full


@then(parsers.parse('OCR 結果應包含商品 "{name}" 恰好 {n:d} 次'))
def result_contains_block(context, name, n):
    assert context["result"].count(f"商品：{name}") == n, context["result"]


@then(parsers.parse('OCR 結果不應包含商品 "{name}"'))
def result_lacks_block(context, name):
    assert f"商品：{name}" not in context["result"]


@then(parsers.parse("頁面分類應被呼叫 {n:d} 次"))
def classify_count(context, n):
    assert context["engine"].classify_calls == n


@then("不帶切片補充規則的 prompt 應為 catalog prompt")
def full_prompt_is_catalog(context):
    full = [
        p for p in context["engine"].prompts if not p.startswith(_SLICE_AWARE_PREFIX)
    ]
    assert full == [_CATALOG_PROMPT]
