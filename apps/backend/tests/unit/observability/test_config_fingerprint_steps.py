"""執行時設定指紋 BDD Step Definitions（Issue #60）"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.observability.config_fingerprint_service import (
    ConfigFingerprintService,
)
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot
from src.domain.bot.value_objects import BotId
from src.domain.observability.effective_config import (
    EffectiveConfig,
    diff_effective_snapshots,
)
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

scenarios("unit/observability/config_fingerprint.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context(monkeypatch):
    captured: list = []
    original = AgentTraceCollector.finish

    def _spy(total_ms=None):
        trace = original(total_ms)
        if trace is not None:
            captured.append(trace)
        return trace

    monkeypatch.setattr(AgentTraceCollector, "finish", staticmethod(_spy))
    yield {"captured": captured}
    AgentTraceCollector.finish(0.0)


def _cfg(**over) -> EffectiveConfig:
    base: dict = {
        "channel": "web",
        "bot_id": "bot-1",
        "system_prompt": "你是客服",
        "platform_prompt_fallback": False,
        "worker_name": "",
        "llm_provider": "anthropic",
        "llm_model": "claude-sonnet-5",
        "router_model": "",
        "llm_params": {"temperature": 0.2, "max_tokens": 400},
        "retrieval": {"modes": ["raw"], "rerank_enabled": False, "kb_ids": ["kb-1"]},
        "enabled_tools": ["rag_query"],
        "max_tool_calls": 5,
        "guard": {"input_rules": [{"id": "r1"}], "output_keywords": [],
                  "blocked_response": "抱歉"},
        "memory_enabled": False,
    }
    base.update(over)
    return EffectiveConfig(**base)


# ── fingerprint purity ──


@given("兩份內容相同但鍵順序不同的有效設定")
def two_same_configs(context):
    a = _cfg(llm_params={"temperature": 0.2, "max_tokens": 400})
    b = _cfg(llm_params={"max_tokens": 400, "temperature": 0.2})
    context["configs"] = [a, b]


@given("一份有效設定")
def one_config(context):
    context["configs"] = [_cfg()]


@given("另一份只在 system_prompt 末尾多一個空白的有效設定")
def config_with_space(context):
    context["configs"].append(_cfg(system_prompt="你是客服 "))


@when("分別計算指紋")
def compute_fingerprints(context):
    context["hashes"] = [c.fingerprint() for c in context["configs"]]


@then(parsers.parse("兩個指紋應相同且長度為 {n:d}"))
def same_hash(context, n):
    a, b = context["hashes"]
    assert a == b and len(a) == n


@then("兩個指紋應不同")
def different_hash(context):
    a, b = context["hashes"]
    assert a != b


@given("一份有效設定其 guard 與 mcp 來源含 api_key 與 line_channel_access_token")
def config_with_secrets(context):
    context["configs"] = [_cfg(
        guard={"input_rules": [], "output_keywords": [], "blocked_response": "抱歉",
               "api_key": "sk-live-123"},
        retrieval={"modes": ["raw"], "kb_ids": [],
                   "line_channel_access_token": "line-token-abc"},
    )]


@when("序列化為 snapshot")
def serialize(context):
    context["snapshot_text"] = json.dumps(
        context["configs"][0].to_snapshot(), ensure_ascii=False
    )


@then(parsers.parse('snapshot 文字不應含 "{a}" 也不應含 "{b}"'))
def snapshot_no_secret(context, a, b):
    assert a not in context["snapshot_text"]
    assert b not in context["snapshot_text"]


# ── recorder ──


@given("指紋紀錄器與可觀察的 repository")
def recorder_with_repo(context):
    repo = AsyncMock()
    repo.ensure = AsyncMock()
    context["repo"] = repo
    context["recorder"] = ConfigFingerprintService(repository=repo)


@given("指紋紀錄器且 repository.ensure 會拋例外")
def recorder_with_failing_repo(context):
    repo = AsyncMock()
    repo.ensure = AsyncMock(side_effect=RuntimeError("db down"))
    context["repo"] = repo
    context["recorder"] = ConfigFingerprintService(repository=repo)


@when("對同一份有效設定紀錄兩次")
def record_twice(context):
    cfg = _cfg()
    context["hashes"] = [
        _run(context["recorder"].record(cfg)),
        _run(context["recorder"].record(cfg)),
    ]


@when("對一份有效設定紀錄一次")
def record_once(context):
    context["hashes"] = [_run(context["recorder"].record(_cfg()))]


@then(parsers.parse("repository.ensure 應只被呼叫 {n:d} 次"))
def ensure_called(context, n):
    assert context["repo"].ensure.await_count == n


@then("兩次回傳的指紋相同")
def hashes_equal(context):
    assert context["hashes"][0] == context["hashes"][1]


@then(parsers.parse("仍應回傳長度 {n:d} 的指紋"))
def hash_len(context, n):
    assert len(context["hashes"][0]) == n


# ── pipelines ──


class _SpyRecorder:
    def __init__(self):
        self.seen: list[EffectiveConfig] = []

    async def record(self, cfg: EffectiveConfig) -> str:
        self.seen.append(cfg)
        return cfg.fingerprint()


@given("一個正常設定的 bot 與已注入的指紋紀錄器")
def web_setup(context):
    bot = Bot(id=BotId(value="bot-1"), tenant_id="t1", name="b", base_prompt="p")
    agent = AsyncMock()
    agent.process_message.return_value = AgentResponse(answer="回答")
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = None
    bot_repo = AsyncMock()
    bot_repo.find_by_id.return_value = bot
    sys_repo = AsyncMock()
    sys_repo.get.return_value = SimpleNamespace(system_prompt="系統")
    context["recorder"] = _SpyRecorder()
    context["uc"] = SendMessageUseCase(
        agent_service=agent,
        conversation_repository=conv_repo,
        bot_repository=bot_repo,
        system_prompt_config_repository=sys_repo,
        config_fingerprint=context["recorder"],
    )


@when(parsers.parse('以來源 "{source}" 送出訊息並攔截 finish 的 trace'))
def web_send(context, source):
    cmd = SendMessageCommand(
        tenant_id="t1", bot_id="bot-1", message="測試", identity_source=source,
    )
    context["response"] = _run(context["uc"].execute(cmd))
    context["trace"] = context["captured"][-1]


@then(parsers.parse("trace.config_hash 應為長度 {n:d} 的字串"))
def trace_has_hash(context, n):
    assert isinstance(context["trace"].config_hash, str)
    assert len(context["trace"].config_hash) == n


@then("回應的 config_hash 應與 trace.config_hash 相同")
def response_hash_matches(context):
    assert context["response"].config_hash == context["trace"].config_hash


@then(parsers.parse('紀錄器收到的有效設定 channel 應為 "{channel}"'))
def recorder_channel(context, channel):
    assert context["recorder"].seen[-1].channel == channel


@given(parsers.parse(
    'Bot "{short_code}" 設定了 LINE Channel、Agent 回覆 "{answer}" 且已注入指紋紀錄器'
))
def line_setup(context, short_code, answer):
    bot = Bot(
        tenant_id="tenant-abc", name="Shop A",
        line_channel_secret="secret-001", line_channel_access_token="token-001",
        knowledge_base_ids=["kb-default"],
    )
    repo = AsyncMock()
    repo.find_by_short_code = AsyncMock(return_value=bot)
    line_service = AsyncMock()
    line_service.verify_signature = AsyncMock(return_value=True)
    factory = MagicMock()
    factory.create = MagicMock(return_value=line_service)
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer=answer))
    context["recorder"] = _SpyRecorder()
    context["short_code"] = short_code
    context["uc"] = HandleWebhookUseCase(
        agent_service=agent, bot_repository=repo, line_service_factory=factory,
        config_fingerprint=context["recorder"],
    )


@when("以 execute_for_bot 處理 LINE 文字事件並攔截 finish 的 trace")
def line_execute(context):
    body = json.dumps({"events": [{
        "type": "message", "replyToken": "tok", "source": {"userId": "U1"},
        "message": {"type": "text", "text": "退貨"}, "timestamp": 1700000000000,
        "webhookEventId": "evt-fp-1",
    }]})
    _run(context["uc"].execute_for_bot(context["short_code"], body, "sig"))
    context["trace"] = context["captured"][-1]


# ── diff ──


@given("兩份 snapshot 僅 llm_model 與 kb_ids 不同")
def two_snapshots(context):
    a = _cfg().to_snapshot()
    b = _cfg(llm_model="gemini-3.7-flash",
             retrieval={"modes": ["raw"], "rerank_enabled": False,
                        "kb_ids": ["kb-2"]}).to_snapshot()
    context["snaps"] = (a, b)


@when("計算 snapshot diff")
def compute_diff(context):
    context["diff"] = diff_effective_snapshots(*context["snaps"])


@then(parsers.parse('diff 應恰好含 "{a}" 與 "{b}" 兩個欄位並附 before/after'))
def diff_fields(context, a, b):
    keys = set(context["diff"].keys())
    assert keys == {a, b}, keys
    for k in (a, b):
        assert "before" in context["diff"][k] and "after" in context["diff"][k]
