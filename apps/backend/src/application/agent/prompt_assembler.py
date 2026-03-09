"""System Prompt 分層組裝器

組裝 Agent 系統提示詞：base_prompt + mode_prompt + bot 自定義指令。
所有 prompt 內容來自 DB（system_prompt_configs 表），由 seed 腳本初始化。
"""


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
        組裝後的完整系統提示詞
    """
    parts: list[str] = []

    if base_prompt:
        parts.append(base_prompt)

    if mode_prompt:
        parts.append(mode_prompt)

    if bot_prompt and bot_prompt.strip():
        parts.append(f"[自定義指令]\n{bot_prompt.strip()}")

    return "\n\n".join(parts)
