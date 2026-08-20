"""Bot 設定快照與 Overlay BDD Step Definitions（純 domain 邏輯，無 mock）"""

import pytest
from pytest_bdd import given, scenarios, then, when

from src.domain.bot.entity import Bot, BotMcpBinding
from src.domain.prompt_gate.config_snapshot import (
    apply_snapshot,
    diff_snapshots,
    take_snapshot,
)

scenarios("unit/prompt_gate/config_snapshot.feature")

_WIDGET_FIELDS = (
    "widget_enabled",
    "widget_allowed_origins",
    "widget_keep_history",
    "widget_welcome_message",
    "widget_placeholder_text",
    "widget_greeting_messages",
    "widget_greeting_animation",
    "fab_icon_url",
)


def _full_bot() -> Bot:
    bot = Bot(
        tenant_id="t1",
        name="測試 bot",
        base_prompt="現行提示詞 {today}",
        bot_prompt="附加指令",
        line_channel_secret="secret-abc",
        line_channel_access_token="token-xyz",
        widget_enabled=True,
        widget_welcome_message="歡迎",
        knowledge_base_ids=["kb-1"],
        eval_provider="anthropic",
        eval_model="claude-haiku",
    )
    return bot


@pytest.fixture
def context():
    return {}


@given("一個完整設定的 Bot（含憑證與 widget 外觀欄位）")
def full_bot(context):
    context["bot"] = _full_bot()


@given("一個綁定了 MCP 且 env_values 含加密金鑰的 Bot")
def bot_with_mcp(context):
    bot = _full_bot()
    bot.mcp_bindings = [
        BotMcpBinding(
            registry_id="reg-1",
            enabled_tools=["search"],
            env_values={"API_KEY": "encrypted-blob"},
        )
    ]
    context["bot"] = bot


@given('一份 base_prompt 為 "舊版提示詞" 且 temperature 為 0.9 的快照')
def snapshot_with_changes(context):
    snap = take_snapshot(context["bot"])
    snap["base_prompt"] = "舊版提示詞"
    snap["llm_params"]["temperature"] = 0.9
    context["snapshot"] = snap


@given("一份只含 base_prompt 的部分快照（模擬舊 schema 版本）")
def partial_snapshot(context):
    context["snapshot"] = {"base_prompt": "舊 schema 提示詞"}


@given("一份含相同 registry_id 的 mcp_bindings 快照")
def mcp_snapshot(context):
    snap = take_snapshot(context["bot"])
    context["snapshot"] = snap
    # 確認快照本身無 env_values（紅線前提）
    assert all("env_values" not in b for b in snap["mcp_bindings"])


@when("對該 Bot 取設定快照")
def do_snapshot(context):
    context["snapshot"] = take_snapshot(context["bot"])


@when("修改 base_prompt 與 temperature 後比較新舊快照")
def do_diff(context):
    from dataclasses import replace

    bot = context["bot"]
    old = take_snapshot(bot)
    bot.base_prompt = "新提示詞"
    bot.llm_params = replace(bot.llm_params, temperature=0.7)
    context["changed"] = diff_snapshots(old, take_snapshot(bot))


@when("將快照 overlay 套用到該 Bot")
def do_apply(context):
    context["result"] = apply_snapshot(context["bot"], context["snapshot"])


@then("快照包含 prompt 類與 LLM 參數與 RAG 檢索與 Agent 行為欄位")
def verify_included(context):
    snap = context["snapshot"]
    for f in (
        "base_prompt", "bot_prompt", "llm_provider", "llm_model",
        "llm_params", "rag_retrieval_modes", "rerank_enabled",
        "enabled_tools", "max_tool_calls", "knowledge_base_ids",
        "tool_configs", "mcp_bindings",
    ):
        assert f in snap, f"快照缺少白名單欄位 {f}"
    assert snap["llm_params"]["temperature"] == 0.3


@then("快照不包含 line_channel_secret 與 line_channel_access_token")
def verify_no_credentials(context):
    snap = context["snapshot"]
    assert "line_channel_secret" not in snap
    assert "line_channel_access_token" not in snap


@then("快照不包含 widget 外觀欄位與 is_active")
def verify_no_widget(context):
    snap = context["snapshot"]
    for f in (*_WIDGET_FIELDS, "is_active"):
        assert f not in snap, f"外觀/營運欄位 {f} 不應入快照"


@then("快照不包含 eval 觀測設定欄位")
def verify_no_eval(context):
    snap = context["snapshot"]
    for f in ("eval_provider", "eval_model", "eval_depth"):
        assert f not in snap


@then("快照的 mcp_bindings 只含 registry_id 與 enabled_tools")
def verify_mcp_shape(context):
    bindings = context["snapshot"]["mcp_bindings"]
    assert bindings == [
        {"registry_id": "reg-1", "enabled_tools": ["search"]}
    ]


@then("快照的 mcp_bindings 不含 env_values")
def verify_mcp_no_env(context):
    for b in context["snapshot"]["mcp_bindings"]:
        assert "env_values" not in b


@then("changed_fields 恰為 base_prompt 與 llm_params.temperature")
def verify_changed_fields(context):
    assert sorted(context["changed"]) == [
        "base_prompt", "llm_params.temperature",
    ]


@then('Bot 的 base_prompt 為 "舊版提示詞" 且 temperature 為 0.9')
def verify_applied(context):
    bot = context["bot"]
    assert bot.base_prompt == "舊版提示詞"
    assert bot.llm_params.temperature == 0.9


@then("Bot 的憑證欄位維持原值")
def verify_credentials_intact(context):
    bot = context["bot"]
    assert bot.line_channel_secret == "secret-abc"
    assert bot.line_channel_access_token == "token-xyz"


@then("Bot 的 base_prompt 為快照值")
def verify_partial_applied(context):
    assert context["bot"].base_prompt == "舊 schema 提示詞"


@then("其餘白名單欄位維持現值")
def verify_others_kept(context):
    bot = context["bot"]
    assert bot.bot_prompt == "附加指令"
    assert bot.knowledge_base_ids == ["kb-1"]
    assert bot.llm_params.temperature == 0.3


@then("回報 skipped_fields 列出快照缺少的欄位")
def verify_skipped(context):
    result = context["result"]
    assert result.applied == ["base_prompt"]
    assert "bot_prompt" in result.skipped
    assert "llm_params" in result.skipped
    assert "mcp_bindings" in result.skipped


@then("Bot 的 mcp_bindings env_values 維持現行加密值")
def verify_env_preserved(context):
    bindings = context["bot"].mcp_bindings
    assert len(bindings) == 1
    assert bindings[0].env_values == {"API_KEY": "encrypted-blob"}
    assert bindings[0].registry_id == "reg-1"
