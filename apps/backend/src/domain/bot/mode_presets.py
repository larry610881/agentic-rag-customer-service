"""情境預設與組合前置條件（Issue #92）

**設計原則：預設只填值，不覆蓋。**

`bot.mode` 曾經是執行期強制覆蓋——kb 模式在管線裡硬關 rerank / 查詢改寫 / HyDE /
記憶 / 工具，導致後台的開關可以打開、存檔成功、實際完全不生效且無任何提示。
本模組把那些行為改成**可組合的欄位**，`mode` 降級為「上次套用的預設」標籤，不驅動行為。

三種語意要分清楚（三者在 UI 上必須長得不一樣）：

* **預設值（本模組的 ``MODE_PRESETS``）** —— 寫入當下填值，之後使用者可任意偏離
* **不變式（如 ``SECURITY_CLAUSE``、guard 的 ``required_stages``）** —— 使用者改不掉，
  且必須讓使用者看得出來被強制
* **前置條件（本模組的 ``PREREQUISITES``）** —— 不是覆蓋，而是「這個選項現在沒有意義」，
  前端在選取當下就 disable 並說明要先開什麼，後端在此守第二層（API 可被直接呼叫）
"""

from __future__ import annotations

from typing import Any, Callable

# 情境預設：套用時一次填好這些欄位，之後就是普通設定
MODE_PRESETS: dict[str, dict[str, Any]] = {
    # 知識庫問答：最短路徑，檢索一次 + 生成一次，未命中直接回話術
    "kb": {
        "direct_retrieval": True,
        "escalate_on_miss": False,
        "rerank_enabled": False,
        "query_rewrite_enabled": False,
        "hyde_enabled": False,
        "memory_enabled": False,
        "enabled_tools": [],
        "eval_depth": "off",
    },
    # 快速道：常見問題直答，未命中才升級推理
    "fast": {
        "direct_retrieval": True,
        "escalate_on_miss": True,
        "rerank_enabled": False,
        "query_rewrite_enabled": False,
        "hyde_enabled": False,
    },
    # 深度道：完整推理與全部能力
    "deep": {
        "direct_retrieval": False,
        "escalate_on_miss": True,
        "rerank_enabled": True,
    },
}

# 前置條件：(欄位, 前置名稱, 判斷式)。判斷式收 bot-like 物件或 dict。
_Getter = Callable[[Any], Any]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


PREREQUISITES: dict[str, tuple[str, str]] = {
    # 欄位 → (前置欄位, 給使用者看的說明)
    "rerank_enabled": ("knowledge_base_ids", "需要先綁定知識庫"),
    "query_rewrite_enabled": ("knowledge_base_ids", "需要先綁定知識庫"),
    "hyde_enabled": ("knowledge_base_ids", "需要先綁定知識庫"),
    # 未命中升級推理，若一個工具都沒有，升級後只是再跑一次同樣的生成，沒有意義
    "escalate_on_miss": ("enabled_tools", "需要先啟用至少一個工具"),
}


def preset_values(mode: str) -> dict[str, Any]:
    """回傳該情境預設要填入的欄位值；未知的 mode 回空 dict（不動任何欄位）。"""
    return dict(MODE_PRESETS.get(mode, {}))


def unmet_prerequisites(bot: Any) -> list[tuple[str, str, str]]:
    """檢查所有已開啟的選項，回傳 (欄位, 前置欄位, 說明) 清單。

    空清單 = 組合有效。前端應在選取當下就 disable 這些選項；本函式是後端第二層防呆。
    """
    unmet: list[tuple[str, str, str]] = []
    for field, (prereq_field, reason) in PREREQUISITES.items():
        if not _get(bot, field, False):
            continue  # 沒開就不必檢查
        if not _get(bot, prereq_field):
            unmet.append((field, prereq_field, reason))
    return unmet
