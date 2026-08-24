"""Regression: LINE 憑證 API 遮罩與 *** 未變更語意（M23）。

GET /bots 回應對 LINE channel secret / access token 一律回 "***"（有值）或
None（未設定），不再回傳原值——任何租戶成員都能 GET，等同憑證外洩面。
表單把 "***" 原封送回時視為未變更（比照 mcp env_values 慣例）；送空字串才清除。
"""

from src.application.bot.update_bot_use_case import (
    UpdateBotCommand,
    UpdateBotUseCase,
)
from src.domain.bot.entity import Bot


def _bot() -> Bot:
    return Bot(
        tenant_id="t1", name="b",
        line_channel_secret="real-secret",
        line_channel_access_token="real-token",
    )


def test_masked_value_keeps_existing_credential():
    bot = _bot()
    UpdateBotUseCase._apply_updates(
        bot,
        UpdateBotCommand(
            bot_id="b1", tenant_id="t1",
            line_channel_secret="***",
            line_channel_access_token="***",
        ),
    )
    assert bot.line_channel_secret == "real-secret"
    assert bot.line_channel_access_token == "real-token"


def test_new_value_replaces_credential():
    bot = _bot()
    UpdateBotUseCase._apply_updates(
        bot,
        UpdateBotCommand(
            bot_id="b1", tenant_id="t1",
            line_channel_secret="new-secret",
        ),
    )
    assert bot.line_channel_secret == "new-secret"
    assert bot.line_channel_access_token == "real-token"  # 未帶 → 不動


def test_empty_string_clears_credential():
    bot = _bot()
    UpdateBotUseCase._apply_updates(
        bot,
        UpdateBotCommand(
            bot_id="b1", tenant_id="t1",
            line_channel_secret="",
        ),
    )
    assert bot.line_channel_secret == ""
