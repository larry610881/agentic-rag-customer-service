"""Embedding token 本地估算（Issue #80）

Gemini 的 OpenAI 相容 ``/embeddings`` 端點不回 ``usage``，記帳路徑拿到 0 就會
整筆略過；供應商沒給數字時改用本地估算補上，呼叫端以
``EmbeddingResult.tokens_estimated`` 得知這是估算值。

估算規則（依可用性擇一，結果都只是近似）：

1. ``tiktoken`` 可匯入且能載入 ``cl100k_base`` → 用其 BPE 計數
   （tiktoken 只是本專案的間接相依，不得假設存在）
2. 否則啟發式：CJK 字元（漢字 / 假名 / 諺文 / 全形符號）每字 1 token，
   其餘字元每 4 個算 1 token（無條件進位）

任何例外一律退回啟發式，估算永遠不能讓 embedding 主流程失敗。
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from functools import lru_cache
from typing import Any

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

_TIKTOKEN_ENCODING = "cl100k_base"

_CJK_RE = re.compile(
    "["
    "\u3000-\u303f"  # CJK 標點
    "\u3040-\u30ff"  # 平假名 / 片假名
    "\u3400-\u4dbf"  # CJK 擴充 A
    "\u4e00-\u9fff"  # CJK 統一漢字
    "\uac00-\ud7af"  # 諺文
    "\uf900-\ufaff"  # CJK 相容漢字
    "\uff00-\uffef"  # 全形字元
    "]"
)


def heuristic_token_count(text: str) -> int:
    """CJK 每字 1 token；其餘字元（含空白）每 4 個 1 token，無條件進位。"""
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    other = len(text) - cjk
    return cjk + math.ceil(other / 4)


@lru_cache(maxsize=1)
def _tiktoken_encoder() -> Any | None:
    try:
        import tiktoken

        return tiktoken.get_encoding(_TIKTOKEN_ENCODING)
    except Exception:  # ImportError / 無法載入 BPE 檔（離線）皆退回啟發式
        logger.info("embedding.token_estimator.tiktoken_unavailable")
        return None


def estimator_name() -> str:
    """記 log 用：實際採用的估算器。"""
    if _tiktoken_encoder() is not None:
        return f"tiktoken:{_TIKTOKEN_ENCODING}"
    return "heuristic"


def estimate_tokens(texts: Iterable[str]) -> int:
    """估算一批文字的 embedding input token 總數（空字串為 0）。"""
    encoder = _tiktoken_encoder()
    total = 0
    for text in texts:
        if not text:
            continue
        if encoder is not None:
            try:
                total += len(encoder.encode(text, disallowed_special=()))
                continue
            except Exception:
                logger.warning("embedding.token_estimator.tiktoken_failed")
        total += heuristic_token_count(text)
    return total
