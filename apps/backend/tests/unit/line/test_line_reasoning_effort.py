"""LINE webhook reasoning_effort 接通測試（Issue #49 / 延遲優化 3）

線上實證：bots.reasoning_effort 欄位存在且 UI 可設定，但聊天路徑
（handle_webhook_use_case → react_agent_service → ChatOpenAI）從未傳遞，
gpt-5 系列一直以 OpenAI 預設 medium reasoning 執行 — 每次 LLM 呼叫
多付 1–2 秒推理延遲。此測試鎖定完整 passthrough 鏈。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.domain.agent.entity import AgentResponse
from src.domain.bot.entity import Bot, BotLLMParams
from src.infrastructure.langgraph.react_agent_service import (
    ReActAgentService,
)
from src.infrastructure.llm.openai_llm_service import OpenAILLMService

BODY = (
    '{"events":[{"type":"message","replyToken":"token-re-001",'
    '"source":{"userId":"U-re-user"},'
    '"message":{"type":"text","text":"測試"},'
    '"timestamp":1700000000000}]}'
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_webhook_passes_reasoning_effort_to_agent():
    """Bot 設定 low 時，llm_params 應帶 reasoning_effort=low 給 agent。"""
    bot = Bot(
        tenant_id="tenant-re",
        name="RE Bot",
        line_channel_secret="secret-re",
        line_channel_access_token="token-re",
        knowledge_base_ids=["kb-re"],
        llm_params=BotLLMParams(reasoning_effort="low"),
    )
    mock_bot_repo = AsyncMock()
    mock_bot_repo.find_by_short_code = AsyncMock(return_value=bot)
    mock_line_service = AsyncMock()
    mock_line_service.verify_signature = AsyncMock(return_value=True)
    mock_factory = MagicMock()
    mock_factory.create = MagicMock(return_value=mock_line_service)
    mock_agent = AsyncMock()
    mock_agent.process_message = AsyncMock(
        return_value=AgentResponse(answer="OK")
    )

    use_case = HandleWebhookUseCase(
        agent_service=mock_agent,
        bot_repository=mock_bot_repo,
        line_service_factory=mock_factory,
    )
    _run(use_case.execute_for_bot("RE01", BODY, "sig"))

    mock_agent.process_message.assert_called_once()
    llm_params = mock_agent.process_message.call_args.kwargs["llm_params"]
    assert llm_params.get("reasoning_effort") == "low"


def test_create_chat_model_sets_none_effort_for_gpt5(monkeypatch):
    """gpt-5 系列 + reasoning_effort='none' → ChatOpenAI 應帶此參數。

    2026-07-21 線上 400 實證：gpt-5.4 綁 function tools 時
    chat completions 只接受 'none'（agent 路徑必綁 tools）。
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model = ReActAgentService._create_chat_model(
        provider="openai",
        model="gpt-5.4",
        reasoning_effort="none",
    )
    assert model.reasoning_effort == "none"


def test_create_chat_model_drops_low_effort_for_gpt5(monkeypatch):
    """gpt-5 + low/medium/high 會被 API 400 拒絕 → 必須略過不傳。

    Regression：部署 low 曾造成 LINE 全面無回應（agent 呼叫全滅）。
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model = ReActAgentService._create_chat_model(
        provider="openai",
        model="gpt-5.4",
        reasoning_effort="low",
    )
    assert model.reasoning_effort is None


def test_create_chat_model_skips_reasoning_effort_for_non_reasoning_model(
    monkeypatch,
):
    """非 reasoning 模型（gpt-4o 系）不得夾帶 reasoning_effort。"""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model = ReActAgentService._create_chat_model(
        provider="openai",
        model="gpt-4o-mini",
        reasoning_effort="low",
    )
    assert model.reasoning_effort is None


def test_openai_llm_service_get_chat_model_passes_none_effort():
    """Dynamic provider 路徑（get_chat_model）也要接通（'none' 放行）。"""
    svc = OpenAILLMService(api_key="sk-test", model="gpt-5.4")
    model = svc.get_chat_model(reasoning_effort="none")
    assert model.reasoning_effort == "none"


def test_openai_llm_service_get_chat_model_drops_low_effort():
    """Dynamic provider 路徑：gpt-5 + low 同樣必須略過（regression）。"""
    svc = OpenAILLMService(api_key="sk-test", model="gpt-5.4")
    model = svc.get_chat_model(reasoning_effort="low")
    assert model.reasoning_effort is None


def test_openai_llm_service_get_chat_model_default_none():
    """未設定時不夾帶（維持 provider 預設行為）。"""
    svc = OpenAILLMService(api_key="sk-test", model="gpt-5.4")
    model = svc.get_chat_model()
    assert model.reasoning_effort is None
