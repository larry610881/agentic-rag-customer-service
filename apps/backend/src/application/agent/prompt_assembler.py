"""System Prompt 分層組裝器

組裝 Agent 系統提示詞：base_prompt + mode_prompt + bot 自定義指令。
所有 prompt 內容來自 DB（system_prompt_configs 表），由 seed 腳本初始化。

支援動態變數（寫在 DB prompt 中，組裝時自動替換）：
  {today}      → 2026-03-09
  {now}        → 2026-03-09 14:30
  {weekday_zh} → 週日
"""

from datetime import datetime, timedelta, timezone

_TZ_TAIPEI = timezone(timedelta(hours=8))

# 中文星期對照
_WEEKDAY_ZH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


def _inject_runtime_vars(prompt: str) -> str:
    """Replace runtime placeholders in the assembled prompt."""
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
    mode: str = "router",
    base_prompt: str = "",
    mode_prompt: str = "",
) -> str:
    """組裝完整的系統提示詞。

    Args:
        bot_prompt: Bot 自定義系統提示詞（可選）
        mode: Agent 模式 ("router" | "react")（未使用，保留向下相容）
        base_prompt: 基礎 prompt（來自 DB）
        mode_prompt: 模式 prompt（來自 DB）

    Returns:
        組裝後的完整系統提示詞（已注入動態變數）
    """
    parts: list[str] = []

    if base_prompt:
        parts.append(base_prompt)

    if mode_prompt:
        parts.append(mode_prompt)

    if bot_prompt and bot_prompt.strip():
        parts.append(f"[自定義指令]\n{bot_prompt.strip()}")

    return _inject_runtime_vars("\n\n".join(parts))
