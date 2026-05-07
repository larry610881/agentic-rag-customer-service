"""SplitPdfUseCase 兩階段順序化 — guard test。

確認 enqueue("process_document", ...) 不在拆頁 loop 內，而是全部拆完
才批次 enqueue。避免 split + OCR 並行搶 worker max_jobs / DB pool /
Milvus → 5/7 carrefour DM 64 頁只切 36 個 child docs 的 root cause。
"""
from __future__ import annotations

import pathlib


def test_split_pdf_use_case_enqueues_after_loop_completes():
    """Source inspection — 確認 enqueue 不在 loop 內。

    若未來 PR 把 enqueue 改回 loop 內（並行 split + OCR），這個 test
    會 fail，提醒 reviewer 重新評估資源爭搶問題。
    """
    src = (
        pathlib.Path(__file__).parents[3]
        / "src" / "application" / "knowledge" / "split_pdf_use_case.py"
    )
    text = src.read_text(encoding="utf-8")

    # 必須有「Phase 1 / Phase 2」結構或對等的兩階段註解
    assert "children_to_enqueue" in text, (
        "split_pdf 必須收集待 enqueue 清單，loop 後批次 enqueue"
    )
    # enqueue("process_document"...) 不應在拆頁 for-loop 內
    # （loop 是 `for png_bytes in iter_pages_as_images(...)`）
    lines = text.splitlines()
    in_loop = False
    loop_indent = 0
    for line in lines:
        stripped = line.lstrip()
        # 抓 for png_bytes in iter_pages_as_images(...) loop 開始
        if stripped.startswith("for png_bytes in iter_pages_as_images"):
            in_loop = True
            loop_indent = len(line) - len(stripped)
            continue
        if in_loop:
            indent = len(line) - len(stripped)
            if stripped and indent <= loop_indent:
                # 退出 loop scope
                in_loop = False
                continue
            # loop 內不允許 enqueue("process_document"
            assert "enqueue(\"process_document\"" not in stripped, (
                "enqueue('process_document') 必須在拆頁 loop 完成後才呼叫，"
                "不可在 loop 內逐頁 enqueue（會造成 split + OCR 並行搶資源）"
            )
