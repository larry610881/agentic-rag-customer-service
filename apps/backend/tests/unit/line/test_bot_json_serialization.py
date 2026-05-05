"""Regression: _bot_to_json / _bot_from_json must round-trip nested dataclasses.

Bug 5/5 (commit 8b9f438 後): tool_configs 在 Redis cache deserialize 後留在
plain dict 形式，而非 ToolRagConfig 實例。LINE webhook 拿 cached bot →
build_tool_rag_params_map → resolve_tool_rag_params → getattr(dict, "rag_top_k")
→ AttributeError → 500。
"""

from datetime import datetime, timezone

from src.application.line.handle_webhook_use_case import (
    _bot_from_json,
    _bot_to_json,
)
from src.domain.bot.entity import (
    Bot,
    BotLLMParams,
    BotMcpBinding,
    IntentRoute,
    McpServerConfig,
    McpToolMeta,
    ToolRagConfig,
)
from src.domain.bot.value_objects import BotId, BotShortCode


def _make_bot_with_nested() -> Bot:
    """產一個帶滿 nested dataclass 的 bot 模擬實戰。"""
    return Bot(
        id=BotId(value="bot-1"),
        short_code=BotShortCode(value="ABCD1234"),
        tenant_id="t-1",
        name="carrefour",
        knowledge_base_ids=["kb-faq", "kb-dm"],
        llm_params=BotLLMParams(temperature=0.5, max_tokens=512),
        mcp_servers=[
            McpServerConfig(
                url="http://mcp.example.com",
                name="example",
                enabled_tools=["tool_a"],
                tools=[McpToolMeta(name="tool_a", description="example tool")],
            )
        ],
        mcp_bindings=[
            BotMcpBinding(registry_id="reg-1", enabled_tools=["tool_a"])
        ],
        intent_routes=[
            IntentRoute(name="客訴", description="客戶抱怨", system_prompt="安撫")
        ],
        tool_configs={
            "rag_query": ToolRagConfig(
                rag_top_k=10, kb_ids=["kb-faq"]
            ),
            "query_dm_with_image": ToolRagConfig(
                rag_top_k=5, kb_ids=["kb-dm"]
            ),
        },
        created_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    )


def test_bot_round_trip_keeps_tool_configs_typed():
    bot = _make_bot_with_nested()
    restored = _bot_from_json(_bot_to_json(bot))
    # 核心斷言：tool_configs 必須是 ToolRagConfig，不是 dict
    for name, cfg in restored.tool_configs.items():
        assert isinstance(cfg, ToolRagConfig), (
            f"tool_configs[{name}] 反序列化後應為 ToolRagConfig，"
            f"實際是 {type(cfg).__name__}"
        )
        # 模擬 resolve_tool_rag_params 的 getattr 呼叫不會炸
        assert hasattr(cfg, "rag_top_k")
        assert hasattr(cfg, "kb_ids")
    assert restored.tool_configs["rag_query"].kb_ids == ["kb-faq"]
    assert restored.tool_configs["query_dm_with_image"].rag_top_k == 5


def test_bot_round_trip_keeps_mcp_servers_typed():
    bot = _make_bot_with_nested()
    restored = _bot_from_json(_bot_to_json(bot))
    assert all(isinstance(s, McpServerConfig) for s in restored.mcp_servers)
    assert all(
        isinstance(t, McpToolMeta) for s in restored.mcp_servers for t in s.tools
    )


def test_bot_round_trip_keeps_mcp_bindings_typed():
    bot = _make_bot_with_nested()
    restored = _bot_from_json(_bot_to_json(bot))
    assert all(isinstance(b, BotMcpBinding) for b in restored.mcp_bindings)


def test_bot_round_trip_keeps_intent_routes_typed():
    bot = _make_bot_with_nested()
    restored = _bot_from_json(_bot_to_json(bot))
    assert all(isinstance(r, IntentRoute) for r in restored.intent_routes)


def test_bot_round_trip_handles_empty_collections():
    bot = Bot(
        id=BotId(value="bot-2"),
        short_code=BotShortCode(value="EMPTY001"),
        tenant_id="t-1",
        created_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    )
    restored = _bot_from_json(_bot_to_json(bot))
    assert restored.tool_configs == {}
    assert restored.mcp_servers == []
    assert restored.mcp_bindings == []
    assert restored.intent_routes == []
