"""SQLAlchemyBotRepository — 租戶過濾條件、寫入內容與實體映射（Issue #101）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

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
from src.infrastructure.db.models.bot_knowledge_base_model import (
    BotKnowledgeBaseModel,
)
from src.infrastructure.db.models.bot_model import BotModel
from src.infrastructure.db.repositories.bot_repository import (
    SQLAlchemyBotRepository,
    _dict_to_tool_configs,
    _tool_configs_to_dict,
)
from tests.unit.repositories.spy_session import SpySession

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _run(coro):
    return asyncio.run(coro)


def _model(**over) -> BotModel:
    data: dict = {
        "id": "bot-1",
        "short_code": "abc123",
        "tenant_id": "tenant-a",
        "name": "客服",
        "description": "desc",
        "is_active": True,
        "bot_prompt": "你是客服",
        "enabled_tools": None,
        "llm_provider": None,
        "llm_model": "gpt-x",
        "show_sources": True,
        "mcp_servers": [
            {
                "url": "http://mcp",
                "name": "m",
                "enabled_tools": ["t1"],
                "tools": [{"name": "t1", "description": "d1"}],
            }
        ],
        "mcp_bindings": [{"registry_id": "r1", "enabled_tools": ["x"]}],
        "max_tool_calls": 3,
        "eval_provider": None,
        "eval_model": None,
        "eval_depth": None,
        "gate_mode": None,
        "mode": None,
        "direct_retrieval": None,
        "escalate_on_miss": None,
        "guard_stages": ["input", "output"],
        "output_format": None,
        "output_schema": {"type": "object"},
        "miss_reply": None,
        "output_text_field": None,
        "gate_soft_threshold": 0.8,
        "gate_repeats": 1,
        "gate_auto_publish": False,
        "gate_daily_limit": 5,
        "gate_budget_usd": 1.0,
        "gate_excluded_cases": None,
        "fab_icon_url": None,
        "widget_enabled": None,
        "widget_allowed_origins": None,
        "widget_keep_history": None,
        "widget_welcome_message": None,
        "widget_placeholder_text": None,
        "widget_greeting_messages": None,
        "widget_greeting_animation": None,
        "memory_enabled": None,
        "memory_extraction_threshold": None,
        "memory_extraction_prompt": None,
        "rerank_enabled": None,
        "rerank_model": None,
        "rerank_top_n": None,
        "rag_retrieval_modes": None,
        "query_rewrite_enabled": None,
        "query_rewrite_model": None,
        "query_rewrite_extra_hint": None,
        "hyde_enabled": None,
        "hyde_model": None,
        "hyde_extra_hint": None,
        "tool_configs": {"rag_query": {"rag_top_k": 8, "kb_ids": ["kb-9"]}},
        "customer_service_url": None,
        "intent_routes": [
            {"name": "退貨", "description": "d", "system_prompt": "舊鍵提示"},
            {"name": "訂單", "worker_prompt": "新鍵提示"},
        ],
        "router_model": None,
        "summary_model": None,
        "busy_reply_message": "請稍候，客服忙線中",
        "line_channel_secret": "sec",
        "line_channel_access_token": "tok",
        "line_show_sources": None,
        "temperature": 0.5,
        "max_tokens": 512,
        "history_limit": 6,
        "frequency_penalty": 0.1,
        "reasoning_effort": "low",
        "rag_top_k": 4,
        "rag_score_threshold": 0.4,
        "created_at": T0,
        "updated_at": T0,
    }
    data.update(over)
    return BotModel(**data)


def _bot(**over) -> Bot:
    data: dict = {
        "id": BotId(value="bot-1"),
        "short_code": BotShortCode(value="abc123"),
        "tenant_id": "tenant-a",
        "name": "新名稱",
        "bot_prompt": "新提示",
        "knowledge_base_ids": ["kb-1", "kb-2"],
        "llm_params": BotLLMParams(temperature=0.9, rag_top_k=7),
        "mcp_servers": [
            McpServerConfig(
                url="http://mcp",
                name="m",
                tools=[McpToolMeta(name="t", description="d")],
            )
        ],
        "mcp_bindings": [BotMcpBinding(registry_id="r1", enabled_tools=["x"])],
        "guard_stages": ["input"],
        "tool_configs": {"rag_query": ToolRagConfig(rag_top_k=3)},
        "intent_routes": [IntentRoute(name="n", description="d", worker_prompt="w")],
        "busy_reply_message": "忙線中，稍後回覆",
    }
    data.update(over)
    return Bot(**data)


@pytest.fixture
def session() -> SpySession:
    return SpySession()


@pytest.fixture
def repo(session) -> SQLAlchemyBotRepository:
    return SQLAlchemyBotRepository(session)  # type: ignore[arg-type]


# ---------------------------------------------------------------- 讀取與映射


def test_find_by_id_maps_entity_and_kb_ids(session, repo):
    session.queue_result([_model()])
    session.queue_result(
        [BotKnowledgeBaseModel(bot_id="bot-1", knowledge_base_id="kb-1")]
    )

    bot = _run(repo.find_by_id("bot-1"))

    assert "bots.id = 'bot-1'" in session.sql(0)
    assert "bot_knowledge_bases.bot_id IN ('bot-1')" in session.sql(1)
    assert bot is not None
    assert bot.tenant_id == "tenant-a"
    assert bot.knowledge_base_ids == ["kb-1"]
    assert bot.llm_params.temperature == 0.5
    assert bot.llm_params.reasoning_effort == "low"
    # None 欄位落回安全預設
    assert bot.enabled_tools == ["rag_query"]
    assert bot.mode == "deep"
    assert bot.gate_mode == "off"
    assert bot.eval_depth == "L1"
    assert bot.widget_enabled is False
    assert bot.widget_keep_history is True
    assert bot.rag_retrieval_modes == ["raw"]
    assert bot.rerank_top_n == 20
    assert bot.memory_extraction_threshold == 3
    assert bot.output_text_field == "answer"
    assert bot.guard_stages == ["input", "output"]
    # 巢狀 JSON 映射
    assert bot.mcp_servers[0].tools[0].name == "t1"
    assert bot.mcp_servers[0].transport == "http"
    assert bot.mcp_bindings[0].registry_id == "r1"
    assert bot.tool_configs["rag_query"].rag_top_k == 8
    assert bot.tool_configs["rag_query"].kb_ids == ["kb-9"]
    # Issue #91：舊 system_prompt 鍵相容
    assert [r.worker_prompt for r in bot.intent_routes] == ["舊鍵提示", "新鍵提示"]
    assert bot.line_channel_secret == "sec"


def test_busy_reply_message_is_loaded_from_db(session, repo):
    """Regression：repository 原本不映射 busy_reply_message → 後台設定永遠顯示預設。"""
    session.queue_result([_model(busy_reply_message="請稍候，客服忙線中")])

    bot = _run(repo.find_by_id("bot-1"))

    assert bot is not None
    assert bot.busy_reply_message == "請稍候，客服忙線中"


def test_find_by_id_missing_returns_none_without_kb_query(session, repo):
    assert _run(repo.find_by_id("nope")) is None
    assert len(session.statements) == 1


def test_find_by_short_code_filters_short_code(session, repo):
    session.queue_result([_model()])
    bot = _run(repo.find_by_short_code("abc123"))
    assert "bots.short_code = 'abc123'" in session.sql(0)
    assert bot is not None and bot.id.value == "bot-1"
    assert _run(repo.find_by_short_code("zzz")) is None


def test_find_all_by_tenant_filters_tenant_and_paginates(session, repo):
    m = _model()
    m.knowledge_bases = [
        BotKnowledgeBaseModel(bot_id="bot-1", knowledge_base_id="kb-3")
    ]
    session.queue_result([m])

    bots = _run(repo.find_all_by_tenant("tenant-a", limit=10, offset=20))

    sql = session.sql()
    assert "bots.tenant_id = 'tenant-a'" in sql
    assert "LIMIT 10" in sql and "OFFSET 20" in sql
    assert bots[0].knowledge_base_ids == ["kb-3"]


def test_find_all_by_tenant_empty(session, repo):
    assert _run(repo.find_all_by_tenant("tenant-a")) == []


def test_find_all_scopes_tenant_only_when_given(session, repo):
    m = _model()
    m.knowledge_bases = []
    session.queue_result([m])
    bots = _run(repo.find_all(tenant_id="tenant-a", limit=5, offset=0))
    assert "bots.tenant_id = 'tenant-a'" in session.sql()
    assert len(bots) == 1

    assert _run(repo.find_all()) == []
    assert "bots.tenant_id =" not in session.sql()


def test_counts_filter_tenant(session, repo):
    session.queue_result([4])
    assert _run(repo.count_by_tenant("tenant-a")) == 4
    assert "bots.tenant_id = 'tenant-a'" in session.sql()

    session.queue_result([2])
    assert _run(repo.count_all(tenant_id="tenant-b")) == 2
    assert "bots.tenant_id = 'tenant-b'" in session.sql()

    session.queue_result([9])
    assert _run(repo.count_all()) == 9
    assert "WHERE" not in session.sql()


def test_exists_for_tenant_requires_both_id_and_tenant(session, repo):
    session.queue_result(["bot-1"])
    assert _run(repo.exists_for_tenant("bot-1", "tenant-a")) is True
    sql = session.sql()
    assert "bots.id = 'bot-1'" in sql and "bots.tenant_id = 'tenant-a'" in sql

    assert _run(repo.exists_for_tenant("bot-1", "tenant-b")) is False


# ---------------------------------------------------------------- 寫入


def test_save_new_bot_adds_model_and_kb_links(session, repo):
    _run(repo.save(_bot()))

    bots = [o for o in session.added if isinstance(o, BotModel)]
    links = [o for o in session.added if isinstance(o, BotKnowledgeBaseModel)]
    assert len(bots) == 1
    m = bots[0]
    assert m.tenant_id == "tenant-a"
    assert m.name == "新名稱"
    assert m.temperature == 0.9 and m.rag_top_k == 7
    assert m.busy_reply_message == "忙線中，稍後回覆"
    assert m.guard_stages == ["input"]
    assert m.tool_configs == {"rag_query": {"rag_top_k": 3}}
    assert m.intent_routes == [
        {"name": "n", "description": "d", "worker_prompt": "w"}
    ]
    assert m.mcp_servers[0]["tools"] == [{"name": "t", "description": "d"}]
    assert sorted(link.knowledge_base_id for link in links) == ["kb-1", "kb-2"]
    # 先清掉舊的 KB 關聯再重建
    assert "DELETE FROM bot_knowledge_bases" in session.sql()
    assert "bot_knowledge_bases.bot_id = 'bot-1'" in session.sql()
    assert session.commits == 1


def test_save_existing_bot_updates_in_place(session, repo):
    existing = _model()
    session.get_result = existing

    _run(repo.save(_bot(guard_stages=None, busy_reply_message="改過的忙碌訊息")))

    assert not [o for o in session.added if isinstance(o, BotModel)]
    assert existing.name == "新名稱"
    assert existing.bot_prompt == "新提示"
    assert existing.temperature == 0.9
    assert existing.guard_stages is None  # None = 繼承平台/租戶設定
    assert existing.busy_reply_message == "改過的忙碌訊息"
    assert existing.tenant_id == "tenant-a"  # 租戶不隨更新改變
    assert existing.updated_at > T0


def test_delete_removes_links_then_bot(session, repo):
    _run(repo.delete("bot-1"))
    first, second = session.all_sql()
    assert "DELETE FROM bot_knowledge_bases" in first
    assert "bot_knowledge_bases.bot_id = 'bot-1'" in first
    assert "DELETE FROM bots" in second and "bots.id = 'bot-1'" in second


# ---------------------------------------------------------------- tool config 序列化


def test_tool_configs_round_trip_drops_none_and_bad_entries():
    raw = {"a": {"rag_top_k": 2, "kb_ids": "not-a-list"}, "b": "junk"}
    parsed = _dict_to_tool_configs(raw)
    assert set(parsed) == {"a"}
    assert parsed["a"].kb_ids is None
    assert _dict_to_tool_configs(None) == {}
    assert _tool_configs_to_dict(parsed) == {"a": {"rag_top_k": 2}}
    assert _tool_configs_to_dict({"empty": ToolRagConfig()}) == {}
