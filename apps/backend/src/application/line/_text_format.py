"""LINE 純文字通路的 Markdown 清除安全網。

LINE 無法渲染 Markdown，LLM 輸出的排版符號會原樣顯示給使用者
（POC 問題 4：回覆出現 ``**`` 符號）。Prompt 已加格式約束，
此 util 為出口端第二層保險 — 只清「確定是排版符號」的模式，
不動單一星號（乘法）與純文字 URL。
"""
from __future__ import annotations

import re

# 成對粗體 **text**（跨行也清）；單一 * 不動
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
# 行首標題 #（1-6 個）+ 空白
_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
# 行首清單符號 - 或 * + 空白 → ・
_LIST_MARKER = re.compile(r"^[ \t]*[-*]\s+", re.MULTILINE)
# Markdown 連結 [text](url) → 「text url」（保留 URL 讓 LINE 自動連結）
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
# 成對 inline code 反引號
_INLINE_CODE = re.compile(r"`([^`\n]*)`")


def strip_markdown_for_line(text: str) -> str:
    """移除 LINE 顯示不了的 Markdown 排版符號，保留內容與 URL。"""
    text = _MD_LINK.sub(r"\1 \2", text)
    text = _BOLD.sub(r"\1", text)
    text = _INLINE_CODE.sub(r"\1", text)
    text = _HEADING.sub("", text)
    text = _LIST_MARKER.sub("・", text)
    return text
