"""Prompt 分層組裝器（Issue #91）

分層定義（順序不可調換）::

    system_prompt    平台防護層 —— 永遠在最前，任何租戶設定都取代不了
    bot_prompt       bot 層 —— 各 bot 自訂；worker 命中時此層由 worker_prompt 取代
    channel_suffix   通路後綴 —— 通路差異只在這裡
    ↓
    effective_prompt 組裝結果，送進模型的字串

**為什麼要延後組裝**：舊版在解析 bot 設定時就把前兩層併成單一字串 ``system_prompt``，
之後任何要換 bot 層的程式碼（worker 覆寫、LINE 通路）只能整串換掉，平台防護層會被
一起洗掉——2026-09-09 實測確認 worker 覆寫與 LINE 兩條路徑都有這個問題。因此設定必須
**分開存** ``system_prompt`` 與 ``bot_prompt``，到使用當下才用本模組組裝。

系統層由兩段組成：``SECURITY_CLAUSE``（程式常數，防護規範，永遠存在）
加上 DB ``system_prompt_configs`` 的平台可調設定（可為空）。

支援動態變數（寫在 DB prompt 中，組裝時自動替換）：
  {today}      → 2026-03-09
  {now}        → 2026-03-09 14:30
  {weekday_zh} → 週日
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from src.domain.platform.prompt_defaults import SECURITY_CLAUSE

_TZ_TAIPEI = timezone(timedelta(hours=8))

# 中文星期對照
_WEEKDAY_ZH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


def inject_runtime_vars(prompt: str) -> str:
    """Replace runtime placeholders ({today}, {now}, {weekday_zh}) in a prompt."""
    now = datetime.now(_TZ_TAIPEI)
    replacements = {
        "{today}": now.strftime("%Y-%m-%d"),
        "{now}": now.strftime("%Y-%m-%d %H:%M"),
        "{weekday_zh}": _WEEKDAY_ZH[now.weekday()],
    }
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)
    return prompt


def assemble(
    bot_prompt: str | None = None,
    system_prompt: str = "",
    channel_suffix: str = "",
) -> str:
    """組裝 effective prompt（送進模型的最終字串）。

    Args:
        bot_prompt: bot 層內容（bot 自訂，或已被 worker_prompt 取代後的值）
        system_prompt: 平台防護層（來自 DB system_prompt_configs）
        channel_suffix: 通路後綴（如 LINE 的格式與長度規範）

    Returns:
        組裝後的 effective prompt（已注入動態變數）
    """
    parts: list[str] = []

    if system_prompt:
        parts.append(system_prompt)

    if bot_prompt and bot_prompt.strip():
        parts.append(f"[自定義指令]\n{bot_prompt.strip()}")

    if channel_suffix and channel_suffix.strip():
        parts.append(channel_suffix.strip())

    return inject_runtime_vars("\n\n".join(parts))


def resolve_bot_layer(base_prompt: str = "", bot_prompt: str = "") -> str:
    """把 bot 的兩個 prompt 欄位合成「bot 層」單一字串。

    ``base_prompt`` 舊語意是「**取代**平台 system prompt」（程式碼寫成
    ``bot.base_prompt or sys_cfg.system_prompt``），等於讓租戶在後台填一個字就能
    關掉平台防護層。Issue #91 起它降級為 bot 層的前段：與 ``bot_prompt`` 同屬
    租戶可編輯範圍，worker 命中時一起被 ``worker_prompt`` 取代，
    **再也影響不到平台防護層**。

    保留欄位而非刪除，是因為 prompt 發布閘門的版控、prompt 優化器的優化目標、
    以及租戶變更稽核都建立在這個欄位上；降級即可達成安全性質，不必動那些功能。
    """
    parts = [p.strip() for p in (base_prompt, bot_prompt) if p and p.strip()]
    return "\n\n".join(parts)


def resolve_effective_prompt(
    cfg: dict[str, Any],
    channel_suffix: str = "",
) -> str:
    """從分層設定組出 effective prompt（**所有通路的唯一組裝入口**）。

    ``cfg`` 必須**分開**存 ``system_prompt``（平台可調設定）與
    ``bot_prompt``（bot 層）；
    這兩個鍵由 ``SendMessageUseCase._resolve_bot_config`` 與 LINE webhook 各自填入，
    三通路共用本函式組裝，確保系統層一字不差。

    ``SECURITY_CLAUSE`` 由本函式**無條件**放在最前面：它是程式常數而非 DB 資料，
    因此 DB 未 seed、租戶把 bot prompt 寫得極簡陋、或 worker 覆寫 bot 層時，
    防護規範都還在。這是 Issue #91 的核心不變式。
    """
    system_layer = SECURITY_CLAUSE
    platform_setting = (cfg.get("system_prompt") or "").strip()
    if platform_setting:
        system_layer = f"{SECURITY_CLAUSE}\n\n{platform_setting}"
    return assemble(
        bot_prompt=cfg.get("bot_prompt") or "",
        system_prompt=system_layer,
        channel_suffix=channel_suffix,
    )


def apply_worker_override(
    cfg: dict[str, Any],
    worker_prompt: str | None,
) -> dict[str, Any]:
    """worker 命中：**只**取代 bot 層，平台防護層原封不動。

    回傳新的 dict，不就地修改傳入的設定。worker 沒有自己的 prompt 時原樣回傳。
    """
    out = dict(cfg)
    if worker_prompt and worker_prompt.strip():
        out["bot_prompt"] = inject_runtime_vars(worker_prompt)
    return out
