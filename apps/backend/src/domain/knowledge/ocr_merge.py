"""切片 OCR × 整頁 OCR 的合併（Issue #82）— 純邏輯，無 I/O。

背景：切片 OCR（2x3 / 3x2）提升字形辨識率，但「半個商品直接省略」規則加
固定 overlap 仍會漏掉橫跨切片邊界的大區塊（DM p13「艾瑪絲 森系列洗髮精」
贈品框整塊消失）。混合模式在切片之外再跑一次整頁 OCR，用本模組合併：

- 解析兩份輸出為 ``(頁面 markers, === blocks, 其他散行)``
- block 身分 = 正規化商品名（去空白 / 標點、全形 → 半形、小寫）；兩份 OCR 對
  同一商品名常有一兩個字形差異（薈 / 著），故相似度 ≥ ``SIMILARITY_THRESHOLD``
  視為同一 block；不同規格變體（350ml / 600ml）相似度不足，仍視為不同
- 共用 block 保留**切片版**（字形較準）；只出現在整頁的 block **補進來**
- 頁面 markers（【頁面標題】【商家】【活動期間】【頁面級促銷說明】【頁面分類】…）
  切片為「不詳」時由整頁補上；切片有值時以切片為準
- 以同一文字格式重新輸出，下游 ``SeparatorTextSplitterService`` 不需改動

格式對照 ``infrastructure/file_parser/ocr_engines/prompts.py::_CATALOG_PROMPT``：
markers 每行 ``【key】value``；每個商品 / 活動為 ``===\\n欄位行…\\n===``。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

UNKNOWN_VALUE = "不詳"
# 正規化商品名的相似度門檻（difflib ratio）：「木之薈樟腦油」vs「木之著樟腦油」
# = 0.83 → 同一商品；「可口可樂350ml」vs「可口可樂600ml」= 0.67 → 不同商品。
SIMILARITY_THRESHOLD = 0.8

_SEPARATOR_RE = re.compile(r"^={3,}\s*$")
_MARKER_LINE_RE = re.compile(r"^【([^】]+)】(.*)$")
# block 身分欄位：商品（catalog / mixed）或活動（promotion / mixed / cover）
_IDENTITY_FIELD_RE = re.compile(r"^(?:商品|活動)[：:]\s*(.*)$")


def normalize_block_key(name: str) -> str:
    """商品名 → 身分 key：NFKC（全形 → 半形）、小寫、去掉所有空白與標點。"""
    folded = unicodedata.normalize("NFKC", name or "").lower()
    return re.sub(r"[\W_]+", "", folded)


@dataclass(frozen=True)
class OcrBlock:
    """一個 ``===`` 包住的商品 / 活動 block（不含分隔線）。"""

    lines: tuple[str, ...]

    @property
    def name(self) -> str:
        for line in self.lines:
            m = _IDENTITY_FIELD_RE.match(line)
            if m:
                return m.group(1).strip()
        return self.lines[0].strip() if self.lines else ""

    @property
    def key(self) -> str:
        """身分 key；空字串或「不詳」代表無法辨識身分。"""
        key = normalize_block_key(self.name)
        return "" if key == normalize_block_key(UNKNOWN_VALUE) else key


@dataclass
class ParsedOcrPage:
    markers: list[tuple[str, str]] = field(default_factory=list)
    blocks: list[OcrBlock] = field(default_factory=list)
    loose_lines: list[str] = field(default_factory=list)

    @property
    def is_structured(self) -> bool:
        return bool(self.markers or self.blocks)


def same_block_identity(key_a: str, key_b: str) -> bool:
    """兩個正規化 key 是否指同一商品：完全相同或相似度 ≥ 門檻（容忍字形差異）。"""
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    return SequenceMatcher(None, key_a, key_b).ratio() >= SIMILARITY_THRESHOLD


def _is_unknown(value: str) -> bool:
    return not value.strip() or value.strip() == UNKNOWN_VALUE


def _put_marker(markers: list[tuple[str, str]], name: str, value: str) -> None:
    """同名 marker 只留一個：第一次出現定順序，值取第一個非「不詳」者。"""
    for i, (existing_name, existing_value) in enumerate(markers):
        if existing_name != name:
            continue
        if _is_unknown(existing_value) and not _is_unknown(value):
            markers[i] = (name, value)
        return
    markers.append((name, value))


def parse_ocr_text(text: str) -> ParsedOcrPage:
    """解析 OCR 文字。

    ``===`` 成對包住 block（與 splitter 的 ``={3,}\\n(.*?)\\n={3,}`` 語意一致）；
    最後一個 block 缺結尾 ``===`` 時仍收下。block 之外的 ``【key】value``
    行為頁面 marker（切片輸出每個 tile 各帶一組，於此去重），其餘非空行
    保留為散行。
    """
    page = ParsedOcrPage()
    in_block = False
    current: list[str] = []

    def _close_block() -> None:
        lines = tuple(line.rstrip() for line in current if line.strip())
        if lines:
            page.blocks.append(OcrBlock(lines))
        current.clear()

    for raw_line in (text or "").splitlines():
        line = raw_line.rstrip()
        if _SEPARATOR_RE.match(line):
            if in_block:
                _close_block()
            in_block = not in_block
            continue
        if in_block:
            current.append(line)
            continue
        if not line.strip():
            continue
        m = _MARKER_LINE_RE.match(line.strip())
        if m:
            _put_marker(page.markers, m.group(1).strip(), m.group(2).strip())
        else:
            page.loose_lines.append(line.strip())

    if in_block:
        _close_block()
    return page


def render_ocr_text(page: ParsedOcrPage) -> str:
    """以 ``_CATALOG_PROMPT`` 範例格式輸出：markers → 散行 → 空行分隔的 blocks。"""
    sections: list[str] = []
    if page.markers:
        sections.append("\n".join(f"【{k}】{v}" for k, v in page.markers))
    if page.loose_lines:
        sections.append("\n".join(page.loose_lines))
    for block in page.blocks:
        sections.append("===\n" + "\n".join(block.lines) + "\n===")
    return "\n\n".join(sections) + ("\n" if sections else "")


def merge_hybrid_ocr_pages(
    sliced: ParsedOcrPage, full_page: ParsedOcrPage
) -> ParsedOcrPage:
    """合併規則：

    1. blocks：切片全部保留（原順序、不互相去重）；整頁 block 的 key 非空且
       與切片任一 block 都不同身分（見 :func:`same_block_identity`）者依整頁
       順序補在後面，同身分只補一次。key 為空 / 「不詳」的整頁 block 無法
       判斷是否重複，不補。
    2. markers：以切片的順序為主、整頁獨有的 marker 接在後面；切片值為
       「不詳」時取整頁的值，否則以切片為準。
    3. 散行：只取切片的（整頁散行視為雜訊）。
    """
    merged = ParsedOcrPage(
        markers=list(sliced.markers),
        blocks=list(sliced.blocks),
        loose_lines=list(sliced.loose_lines),
    )
    for name, value in full_page.markers:
        _put_marker(merged.markers, name, value)

    seen = [b.key for b in sliced.blocks if b.key]
    for block in full_page.blocks:
        key = block.key
        if not key or any(same_block_identity(key, k) for k in seen):
            continue
        seen.append(key)
        merged.blocks.append(block)
    return merged


def merge_hybrid_ocr_text(sliced_text: str, full_page_text: str) -> str:
    """文字進、文字出的合併入口。

    兩邊都沒有 marker / block（非結構化 prompt）時原樣回傳切片結果，
    避免把 general 模式的純文字重排。
    """
    sliced = parse_ocr_text(sliced_text)
    full_page = parse_ocr_text(full_page_text)
    if not sliced.is_structured and not full_page.is_structured:
        return sliced_text
    return render_ocr_text(merge_hybrid_ocr_pages(sliced, full_page))
