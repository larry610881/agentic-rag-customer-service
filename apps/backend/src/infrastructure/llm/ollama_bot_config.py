# ============================================================
# HARDCODE - 僅供地端模型 A/B 測試使用，正式上線前必須移除
# 移除時一併刪除：
#   - 此檔案
#   - update_bot_use_case.py 的 get_ollama_model_for_bot import 與呼叫
#   - container.py 的 ollama_warm_up provider 與注入
#   - bot_router.py 的 warm_up_status 欄位與解包
# ============================================================

"""Ollama 測試用 hardcode 設定 [HARDCODE - REMOVE BEFORE PRODUCTION]

Bot 名稱 → Ollama 模型的對應。
單一使用者測試場景，不走 DB provider settings。
"""

# Bot 名稱（完全比對）→ Ollama 模型
# HARDCODE - REMOVE BEFORE PRODUCTION
OLLAMA_BOT_MODEL_MAP: dict[str, str] = {
    "家樂福subagent測試": "qwen3.6:35b-a3b",  # HARDCODE - 切換此處模型進行 A/B 測試
}


def get_ollama_model_for_bot(bot_name: str) -> str | None:
    """依 bot 名稱取得 hardcode 的 Ollama 模型，找不到回傳 None。
    HARDCODE - REMOVE BEFORE PRODUCTION
    """
    return OLLAMA_BOT_MODEL_MAP.get(bot_name)
