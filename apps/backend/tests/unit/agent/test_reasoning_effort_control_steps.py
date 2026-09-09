"""推理強度控制 BDD Step Definitions（Issue #72）

涵蓋：none 值域（create / update）、三通路 llm_params 對等（含 worker 覆寫與快速道）、
供應商對應（OpenAI / Gemini / Anthropic LangChain 與原生 body）、有效值解析、
稽核視圖 / 快照 / 指紋、trace 節點 requested vs effective、reasoning_tokens。
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from langchain_core.messages import AIMessage
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.agent.direct_retrieval_service import DirectRetrievalService
from src.application.agent.intent_classifier import ClassifyOutcome
from src.application.agent.send_message_use_case import (
    SendMessageCommand,
    SendMessageUseCase,
)
from src.application.bot.create_bot_use_case import (
    CreateBotCommand,
    CreateBotUseCase,
)
from src.application.bot.update_bot_use_case import (
    UpdateBotCommand,
    UpdateBotUseCase,
)
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.rag.query_rag_use_case import RetrieveResult
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.value_objects import BotId
from src.domain.bot.worker_config import WorkerConfig
from src.domain.observability.agent_trace import AgentExecutionTrace
from src.domain.observability.effective_config import EffectiveConfig
from src.domain.prompt_gate.config_snapshot import diff_snapshots, take_snapshot
from src.domain.rag.value_objects import Source
from src.domain.shared.exceptions import ValidationError
from src.infrastructure.langgraph.react_agent_service import ReActAgentService
from src.infrastructure.langgraph.usage import (
    build_usage_event,
    extract_usage_from_langchain_messages,
)
from src.infrastructure.llm.anthropic_llm_service import AnthropicLLMService
from src.infrastructure.llm.openai_llm_service import (
    OpenAILLMService,
    invalidate_unsupported_param_cache,
)
from src.infrastructure.llm.reasoning_effort import effective_reasoning_effort
from src.infrastructure.observability.agent_trace_collector import (
    AgentTraceCollector,
)

scenarios("unit/agent/reasoning_effort_control.feature")

_OMIT = "(省略)"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    invalidate_unsupported_param_cache()
    yield
    invalidate_unsupported_param_cache()


# ── A. 值域 ──


@given("bot 建立用例")
def create_uc(context):
    repo = AsyncMock()
    repo.save = AsyncMock()
    context["create_uc"] = CreateBotUseCase(bot_repository=repo)
    context["repo"] = repo


@when(parsers.parse('以推理強度 "{effort}" 建立 bot'))
def create_bot(context, effort):
    try:
        bot = _run(context["create_uc"].execute(CreateBotCommand(
            tenant_id="t1", name="B", reasoning_effort=effort,
        )))
        context["outcome"] = "saved"
        context["saved"] = bot.llm_params.reasoning_effort
    except (ValidationError, ValueError):
        context["outcome"] = "error"


@then(parsers.parse("建立結果應為 {outcome}"))
def create_outcome(context, outcome):
    assert context["outcome"] == outcome
    if outcome == "saved":
        context["repo"].save.assert_awaited_once()


@given(parsers.parse('一個推理強度為 "{effort}" 的既有 bot'))
def existing_bot(context, effort):
    bot = Bot(
        id=BotId(value="bot-r"), tenant_id="t1", name="R",
        llm_params=BotLLMParams(reasoning_effort=effort),
    )
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=bot)
    repo.save = AsyncMock()
    context["bot"] = bot
    context["update_uc"] = UpdateBotUseCase(bot_repository=repo)


@when(parsers.parse('將 bot 推理強度更新為 "{effort}"'))
def update_effort(context, effort):
    try:
        _run(context["update_uc"].execute(
            UpdateBotCommand(bot_id="bot-r", reasoning_effort=effort)
        ))
        context["outcome"] = "saved"
    except (ValidationError, ValueError):
        context["outcome"] = "error"


@then(parsers.parse('更新結果應為 {outcome} 且儲存的推理強度為 "{stored}"'))
def update_outcome(context, outcome, stored):
    assert context["outcome"] == outcome
    assert context["bot"].llm_params.reasoning_effort == stored


@when("只更新 bot 名稱")
def update_name_only(context):
    _run(context["update_uc"].execute(UpdateBotCommand(bot_id="bot-r", name="R2")))


@then(parsers.parse('儲存的推理強度應為 "{stored}"'))
def stored_effort(context, stored):
    assert context["bot"].llm_params.reasoning_effort == stored


# ── B. 通路對等 ──


def _sources(score):
    return [Source(
        document_name="FAQ", content_snippet="板橋店 2 樓設有快剪",
        score=score, chunk_id="c-1",
    )]


def _bot(effort, *, mode="deep"):
    return Bot(
        id=BotId(value="bot-e"), tenant_id="t1", name="E", knowledge_base_ids=["kb-1"], mode=mode,
        line_channel_secret="s", line_channel_access_token="t",
        llm_params=BotLLMParams(reasoning_effort=effort),
    )


def _workers(worker_model):
    if worker_model is None:
        return []
    return [WorkerConfig(
        bot_id="bot-e", name="門市", worker_prompt="你是門市客服",
        knowledge_base_ids=["kb-1"], llm_provider="openai", llm_model=worker_model,
        enabled_tools=["rag_query"],
    )]


def _classifier(workers):
    classifier = AsyncMock()
    classifier.classify_sanitize = AsyncMock(return_value=ClassifyOutcome(
        worker=workers[0] if workers else None, query="", is_attack=False,
    ))
    return classifier


def _setup_channels(context, *, effort, worker_model=None, mode="deep", score=0.85):
    bot = _bot(effort, mode=mode)
    workers = _workers(worker_model)
    agent = AsyncMock()
    agent.process_message = AsyncMock(return_value=AgentResponse(answer="答"))
    query_rag = AsyncMock()
    query_rag.retrieve = AsyncMock(return_value=RetrieveResult(
        chunks=["板橋店 2 樓設有快剪"], sources=_sources(score),
    ))
    worker_repo = AsyncMock()
    worker_repo.find_by_bot_id = AsyncMock(return_value=workers)
    context["agent"] = agent

    # web / widget
    conv_repo = AsyncMock()
    conv_repo.find_by_id.return_value = None
    bot_repo = AsyncMock()
    bot_repo.find_by_id.return_value = bot
    sys_repo = AsyncMock()
    sys_repo.get.return_value = SimpleNamespace(system_prompt="系統")
    context["uc"] = SendMessageUseCase(
        agent_service=agent,
        conversation_repository=conv_repo,
        bot_repository=bot_repo,
        system_prompt_config_repository=sys_repo,
        intent_classifier=_classifier(workers),
        worker_config_repo=worker_repo,
        direct_retrieval_service=DirectRetrievalService(query_rag_use_case=query_rag),
    )

    # LINE
    line_bot_repo = AsyncMock()
    line_bot_repo.find_by_short_code = AsyncMock(return_value=bot)
    line_service = AsyncMock()
    line_service.verify_signature = AsyncMock(return_value=True)
    factory = MagicMock()
    factory.create = MagicMock(return_value=line_service)
    context["line_uc"] = HandleWebhookUseCase(
        agent_service=agent, bot_repository=line_bot_repo,
        line_service_factory=factory,
        intent_classifier=_classifier(workers),
        worker_config_repo=worker_repo,
        direct_retrieval_service=DirectRetrievalService(query_rag_use_case=query_rag),
    )


@given(parsers.parse('一個推理強度為 "{effort}" 且沒有 worker 的 bot'))
def bot_no_worker(context, effort):
    _setup_channels(context, effort=effort)


@given(parsers.parse('一個推理強度為 "{effort}" 且 worker 指定模型 "{model}" 的 bot'))
def bot_with_worker(context, effort, model):
    _setup_channels(context, effort=effort, worker_model=model)


@given(parsers.parse(
    '一個 mode 為 "{mode}" 且推理強度為 "{effort}" 的 bot，檢索分數 {score:g}'
))
def fast_bot(context, mode, effort, score):
    _setup_channels(context, effort=effort, mode=mode, score=score)


@when(parsers.parse('以 "{channel}" 通路送出訊息'))
def send_via(context, channel):
    if channel == "line":
        body = json.dumps({"events": [{
            "type": "message", "replyToken": "tok", "source": {"userId": "U1"},
            "message": {"type": "text", "text": "板橋店有快剪嗎"},
            "timestamp": 1700000000000, "webhookEventId": "evt-re-1",
        }]})
        _run(context["line_uc"].execute_for_bot("shop", body, "sig"))
        return
    cmd = SendMessageCommand(
        tenant_id="t1", bot_id="bot-e", message="板橋店有快剪嗎",
        identity_source="widget" if channel == "widget" else None,
        visitor_id="v-1" if channel == "widget" else None,
    )
    _run(context["uc"].execute(cmd))


def _agent_llm_params(context):
    context["agent"].process_message.assert_called()
    return context["agent"].process_message.call_args.kwargs["llm_params"]


@then(parsers.parse('Agent 收到的 llm_params 應含 reasoning_effort "{effort}"'))
def agent_effort(context, effort):
    assert _agent_llm_params(context).get("reasoning_effort") == effort


@then(parsers.parse('Agent 收到的 llm_params 模型應為 "{model}"'))
def agent_model(context, model):
    assert _agent_llm_params(context).get("model") == model


@then(parsers.parse("Agent 應以 max_tool_calls {n:d} 被呼叫"))
def agent_max_tool_calls(context, n):
    assert context["agent"].process_message.call_args.kwargs["max_tool_calls"] == n


# ── C. 供應商對應 ──


@when(parsers.parse(
    '以供應商 "{provider}" 模型 "{model}" 建立聊天模型並要求推理強度 "{effort}"'
))
def build_chat_model(context, provider, model, effort):
    context["chat_model"] = ReActAgentService._create_chat_model(
        provider=provider, model=model, reasoning_effort=effort,
    )


def _expect(value: str):
    return None if value == _OMIT else value


@then(parsers.parse('聊天模型送出的 reasoning_effort 應為 "{sent}"'))
def openai_sent(context, sent):
    assert context["chat_model"].reasoning_effort == _expect(sent)


def _thinking_type(thinking):
    return None if thinking is None else thinking.get("type")


@then(parsers.parse(
    'Anthropic 聊天模型的 thinking 應為 "{thinking}" 且 effort 應為 "{sent}"'
))
def anthropic_chat_model(context, thinking, sent):
    m = context["chat_model"]
    assert _thinking_type(m.thinking) == _expect(thinking), m.thinking
    assert m.reasoning_effort == _expect(sent)


@when(parsers.parse(
    '以 Anthropic 模型 "{model}" 產生請求本體並要求推理強度 "{effort}"'
))
def anthropic_body(context, model, effort):
    svc = AnthropicLLMService(api_key="sk-ant-test", model=model)
    context["body"] = svc._build_body("s", "u", "", reasoning_effort=effort)


@then(parsers.parse(
    '請求本體的 thinking 應為 "{thinking}" 且 output_config.effort 應為 "{sent}"'
))
def anthropic_body_check(context, thinking, sent):
    body = context["body"]
    assert _thinking_type(body.get("thinking")) == _expect(thinking)
    assert (body.get("output_config") or {}).get("effort") == _expect(sent)


@given("Anthropic 服務回應含 thinking 區塊與文字區塊")
def anthropic_thinking_response(context):
    svc = AnthropicLLMService(api_key="sk-ant-test", model="claude-opus-5")
    client = MagicMock()
    client.post = AsyncMock(return_value=httpx.Response(
        status_code=200,
        json={
            "content": [
                {"type": "thinking", "thinking": "先看 FAQ"},
                {"type": "text", "text": "板橋店 2 樓設有快剪"},
            ],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        },
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    ))
    svc._client = client
    context["anthropic"] = svc
    context["post"] = client.post


@when(parsers.parse('以推理強度 "{effort}" 呼叫 Anthropic generate'))
def anthropic_generate(context, effort):
    context["result"] = _run(context["anthropic"].generate(
        system_prompt="s", user_message="板橋店有快剪嗎", context="",
        reasoning_effort=effort,
    ))


@then(parsers.parse('回傳文字應為 "{text}"'))
def result_text(context, text):
    assert context["result"].text == text
    sent = context["post"].await_args.kwargs["json"]
    assert sent["thinking"] == {"type": "adaptive"}
    assert sent["output_config"]["effort"] == "high"


@when(parsers.parse(
    '以供應商 "{provider}" 模型 "{model}" 解析推理強度要求值 "{effort}"'
))
def resolve_effective(context, provider, model, effort):
    context["effective"] = effective_reasoning_effort(provider, model, effort)


@then(parsers.parse('有效推理強度應為 "{effective}"'))
def effective_check(context, effective):
    assert context["effective"] == effective


# ── D. 審計 / 指紋 / trace / usage ──


@given(parsers.parse('一個推理強度為 "{effort}" 的 bot 實體'))
def bot_entity(context, effort):
    context["entity"] = Bot(
        tenant_id="t1", name="A", llm_params=BotLLMParams(reasoning_effort=effort),
    )


@when(parsers.parse('取快照後把推理強度改為 "{effort}" 再取一次快照'))
def snapshot_change(context, effort):
    bot = context["entity"]
    context["before"] = take_snapshot(bot)
    bot.llm_params.reasoning_effort = effort
    context["after"] = take_snapshot(bot)


@then(parsers.parse('稽核視圖的 llm_params.reasoning_effort 應為 "{effort}"'))
def audit_view_effort(context, effort):
    view = UpdateBotUseCase._audit_view(context["entity"])
    assert view["llm_params"]["reasoning_effort"] == effort


@then(parsers.parse('快照 diff 應列出 "{field}"'))
def snapshot_diff(context, field):
    assert field in diff_snapshots(context["before"], context["after"])


def _effective_config(effort):
    return EffectiveConfig(
        channel="web", bot_id="bot-e", system_prompt="p",
        llm_provider="openai", llm_model="gpt-5.4",
        llm_params={"temperature": 0.3, "reasoning_effort": effort},
    )


@given("兩份僅推理強度不同（medium 與 none）的有效設定")
def two_configs(context):
    context["cfg_medium"] = _effective_config("medium")
    context["cfg_none"] = _effective_config("none")


@then("兩者的指紋應不同")
def fingerprints_differ(context):
    assert context["cfg_medium"].fingerprint() != context["cfg_none"].fingerprint()


@then(parsers.parse(
    '兩份快照的 llm_params.reasoning_effort 應分別為 "{a}" 與 "{b}"'
))
def snapshots_effort(context, a, b):
    assert context["cfg_medium"].to_snapshot()["llm_params"]["reasoning_effort"] == a
    assert context["cfg_none"].to_snapshot()["llm_params"]["reasoning_effort"] == b


def _ai_message(reasoning: int) -> AIMessage:
    return AIMessage(
        content="答",
        usage_metadata={
            "input_tokens": 10, "output_tokens": 50, "total_tokens": 60,
            "output_token_details": {"reasoning": reasoning},
        },
        response_metadata={"model_name": "gpt-5.4"},
    )


@given(parsers.parse(
    '一個 ReAct 執行，供應商 "{provider}" 模型 "{model}" 要求推理強度 "{effort}"'
))
def react_setup(context, provider, model, effort):
    context["service"] = ReActAgentService(
        llm_service=AsyncMock(), rag_tool=AsyncMock(),
    )
    context["llm_params"] = {
        "provider_name": provider, "model": model, "reasoning_effort": effort,
    }


@when("執行一次 agent 回覆")
def react_run(context):
    service = context["service"]
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.ainvoke = AsyncMock(return_value=_ai_message(40))

    async def _go():
        with (
            patch.object(
                service, "_resolve_llm_model", new=AsyncMock(return_value=llm),
            ),
            patch.object(service, "_build_builtin_tools", return_value=[]),
        ):
            await service.process_message(
                tenant_id="t1", kb_id="kb-1", user_message="hi",
                llm_params=context["llm_params"], enabled_tools=[],
            )
            trace = AgentTraceCollector.current()
            assert trace is not None
            return [n for n in trace.nodes if n.node_type == "agent_llm"]

    nodes = _run(_go())
    assert len(nodes) == 1, [n.node_type for n in nodes]
    context["node"] = nodes[0]


@then(parsers.parse('agent_llm 節點的 reasoning_effort_requested 應為 "{value}"'))
def node_requested(context, value):
    assert context["node"].metadata["reasoning_effort_requested"] == value


@then(parsers.parse('agent_llm 節點的 reasoning_effort_effective 應為 "{value}"'))
def node_effective(context, value):
    assert context["node"].metadata["reasoning_effort_effective"] == value


@then(parsers.parse("agent_llm 節點的 token_usage.reasoning_tokens 應為 {n:d}"))
def node_reasoning_tokens(context, n):
    assert context["node"].token_usage["reasoning_tokens"] == n


@given(parsers.parse("一則 output_token_details.reasoning 為 {n:d} 的 AIMessage"))
def ai_message(context, n):
    context["messages"] = [_ai_message(n)]


@when("從 LangChain 訊息擷取 usage")
def extract_usage(context):
    context["usage"] = extract_usage_from_langchain_messages(context["messages"])


@then(parsers.parse("usage 的 reasoning_tokens 應為 {n:d}"))
def usage_reasoning(context, n):
    assert context["usage"].reasoning_tokens == n
    # 不重複計入 total（reasoning 已含在 output_tokens）
    assert context["usage"].total_tokens == 60


@then(parsers.parse("usage 事件的 reasoning_tokens 應為 {n:d}"))
def usage_event_reasoning(context, n):
    assert build_usage_event(context["usage"])["reasoning_tokens"] == n


@given(parsers.parse(
    "OpenAI 服務回應 usage.completion_tokens_details.reasoning_tokens 為 {n:d}"
))
def openai_reasoning_response(context, n):
    svc = OpenAILLMService(api_key="sk-test", model="gpt-5-nano")
    client = MagicMock()
    client.post = AsyncMock(return_value=httpx.Response(
        status_code=200,
        json={
            "choices": [{"message": {"content": "商品查詢"}}],
            "usage": {
                "prompt_tokens": 100, "completion_tokens": 40,
                "completion_tokens_details": {"reasoning_tokens": n},
            },
        },
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    ))
    svc._client = client
    context["openai"] = svc


@when(parsers.parse('以推理強度 "{effort}" 呼叫 OpenAI generate'))
def openai_generate(context, effort):
    context["result"] = _run(context["openai"].generate(
        system_prompt="分類", user_message="q", context="", reasoning_effort=effort,
    ))


@then(parsers.parse("回傳 usage 的 reasoning_tokens 應為 {n:d}"))
def result_reasoning(context, n):
    assert context["result"].usage.reasoning_tokens == n


@given(parsers.parse(
    "一個 trace 含兩個 agent_llm 節點，reasoning_tokens 分別為 {a:d} 與 {b:d}"
))
def trace_with_nodes(context, a, b):
    trace = AgentExecutionTrace(tenant_id="t1", agent_mode="react")
    for i, r in enumerate((a, b)):
        trace.add_node(
            node_type="agent_llm", label=f"迭代 {i + 1}", parent_id=None,
            start_ms=0.0, end_ms=1.0,
            token_usage={
                "input_tokens": 10, "output_tokens": 20, "reasoning_tokens": r,
            },
        )
    context["trace"] = trace


@when("trace 完成")
def trace_finish(context):
    context["trace"].finish(100.0)


@then(parsers.parse("trace total_tokens 的 reasoning_tokens 應為 {n:d}"))
def trace_total_reasoning(context, n):
    assert context["trace"].total_tokens["reasoning_tokens"] == n
