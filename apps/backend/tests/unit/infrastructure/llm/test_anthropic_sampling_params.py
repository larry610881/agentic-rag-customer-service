"""Issue #76：Anthropic 依模型決定是否送 temperature / top_p / top_k

依 claude-api skill：
- shared/error-codes.md「Model-specific 400s on Claude Opus 5 / Fable 5/5.1 /
  Opus 4.8 / 4.7」：temperature / top_p / top_k 送任一即 400。
- shared/model-migration.md §Migrating to Sonnet 5：非預設值 400 → 本專案一律不送。
- Opus 4.6 / Sonnet 4.6 / 4.5 / 4.x / 3.x：允許；未知模型視為允許。

三條路徑都要守：raw httpx `_build_body`、`get_chat_model`（ChatAnthropic）、
`react_agent_service._create_chat_model` 的 Anthropic 分支。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from langchain_core.messages import HumanMessage

from src.infrastructure.langgraph.react_agent_service import ReActAgentService
from src.infrastructure.llm import anthropic_llm_service as svc_module
from src.infrastructure.llm.anthropic_llm_service import (
    AnthropicLLMService,
    anthropic_sampling_kwargs,
)
from src.infrastructure.llm.reasoning_effort import sampling_params_allowed


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── 1. 表驅動：sampling_params_allowed ──

_TABLE = [
    # 送任一即 400（error-codes.md / model-migration.md Opus 4.7 §Sampling removed）
    ("claude-opus-4-7", False),
    ("claude-opus-4-8", False),
    ("claude-opus-5", False),
    ("claude-fable-5", False),
    ("claude-fable-5-1", False),
    ("claude-mythos-5", False),
    ("claude-mythos-5-1", False),
    ("claude-mythos-preview", False),
    # Sonnet 5：只收預設值 → 不送
    ("claude-sonnet-5", False),
    # 允許（Thinking & Effort 表 Sampling = Allowed）
    ("claude-opus-4-6", True),
    ("claude-sonnet-4-6", True),
    ("claude-opus-4-5", True),
    ("claude-opus-4-5-20251101", True),
    ("claude-sonnet-4-5", True),
    ("claude-sonnet-4-5-20250929", True),
    ("claude-haiku-4-5", True),
    ("claude-sonnet-4-20250514", True),
    ("claude-opus-4-1", True),
    ("claude-3-7-sonnet-20250219", True),
    ("claude-3-5-haiku-20241022", True),
    # Bedrock / Vertex 前綴仍依 claude-* 本體判斷
    ("anthropic.claude-opus-5", False),
    ("us.anthropic.claude-opus-4-7", False),
    ("anthropic.claude-sonnet-4-6", True),
    # 未知 / 空字串 → 維持既有行為（允許）
    ("claude-unknown-9", True),
    ("", True),
]


@pytest.mark.parametrize(("model", "allowed"), _TABLE)
def test_sampling_params_allowed_table(model: str, allowed: bool):
    assert sampling_params_allowed(model) is allowed


def test_sampling_prefix_does_not_swallow_neighbouring_versions():
    """claude-sonnet-5 前綴不可誤傷 sonnet-4-5；claude-opus-5 不可誤傷 opus-4-5。"""
    assert sampling_params_allowed("claude-sonnet-4-5") is True
    assert sampling_params_allowed("claude-opus-4-5") is True
    assert sampling_params_allowed("claude-sonnet-5") is False
    assert sampling_params_allowed("claude-opus-5") is False


# ── 2. anthropic_sampling_kwargs：丟棄 + log ──


def test_sampling_kwargs_keeps_all_on_allowed_model():
    assert anthropic_sampling_kwargs(
        "claude-sonnet-4-6", temperature=0.3, top_p=0.9, top_k=40
    ) == {"temperature": 0.3, "top_p": 0.9, "top_k": 40}


def test_sampling_kwargs_omits_unrequested_params():
    assert anthropic_sampling_kwargs("claude-sonnet-4-6", temperature=0.3) == {
        "temperature": 0.3
    }
    assert anthropic_sampling_kwargs("claude-sonnet-4-6") == {}


def test_sampling_kwargs_drops_all_and_logs_on_opus47(monkeypatch):
    logged: list[dict] = []
    fake_logger = MagicMock()
    fake_logger.warning = lambda event, **kw: logged.append({"event": event, **kw})
    monkeypatch.setattr(svc_module, "logger", fake_logger)

    out = anthropic_sampling_kwargs(
        "claude-opus-4-7", temperature=0.7, top_p=0.9, top_k=40
    )

    assert out == {}
    assert [e["event"] for e in logged] == ["llm.temperature.dropped"] * 3
    assert {e["param"]: e["requested"] for e in logged} == {
        "temperature": 0.7, "top_p": 0.9, "top_k": 40,
    }
    assert all(e["model"] == "claude-opus-4-7" for e in logged)


def test_sampling_kwargs_no_log_when_nothing_requested(monkeypatch):
    fake_logger = MagicMock()
    monkeypatch.setattr(svc_module, "logger", fake_logger)
    assert anthropic_sampling_kwargs("claude-opus-5") == {}
    fake_logger.warning.assert_not_called()


# ── 3. raw httpx 路徑：_build_body / generate ──


def _make_anthropic(model: str) -> tuple[AnthropicLLMService, AsyncMock]:
    svc = AnthropicLLMService(api_key="sk-ant-test", model=model)
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=httpx.Response(
        status_code=200,
        json={
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 5, "output_tokens": 7},
        },
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    ))
    svc._client = mock_client
    return svc, mock_client.post


@pytest.mark.parametrize("model", [
    "claude-opus-4-7", "claude-opus-4-8", "claude-opus-5",
    "claude-fable-5-1", "claude-sonnet-5",
])
def test_build_body_omits_temperature_on_no_sampling_models(model: str):
    svc, _ = _make_anthropic(model)
    body = svc._build_body("s", "q", "", temperature=0.2)
    assert "temperature" not in body
    assert "top_p" not in body
    assert "top_k" not in body


@pytest.mark.parametrize("model", [
    "claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5",
    "claude-sonnet-4-20250514",
])
def test_build_body_keeps_temperature_on_allowed_models(model: str):
    svc, _ = _make_anthropic(model)
    body = svc._build_body("s", "q", "", temperature=0.2)
    assert body["temperature"] == 0.2


def test_generate_on_opus5_sends_no_temperature_and_logs(monkeypatch):
    logged: list[dict] = []
    fake_logger = MagicMock()
    fake_logger.warning = lambda event, **kw: logged.append({"event": event, **kw})
    fake_logger.bind = lambda **kw: fake_logger
    monkeypatch.setattr(svc_module, "logger", fake_logger)

    svc, post = _make_anthropic("claude-opus-5")
    _run(svc.generate(system_prompt="s", user_message="q", context="", temperature=0.5))

    body = post.await_args.kwargs["json"]
    assert "temperature" not in body
    assert body["model"] == "claude-opus-5"
    drops = [e for e in logged if e["event"] == "llm.temperature.dropped"]
    assert len(drops) == 1
    assert drops[0]["model"] == "claude-opus-5"
    assert drops[0]["requested"] == 0.5
    assert drops[0]["param"] == "temperature"


def test_generate_on_sonnet46_still_sends_temperature():
    svc, post = _make_anthropic("claude-sonnet-4-6")
    _run(svc.generate(system_prompt="s", user_message="q", context="", temperature=0.5))
    assert post.await_args.kwargs["json"]["temperature"] == 0.5


# ── 4. LangChain 路徑：get_chat_model / _create_chat_model ──


def _payload(chat_model) -> dict:
    return chat_model._get_request_payload([HumanMessage("hi")])


def _wire_sampling(payload: dict) -> dict:
    """langchain-anthropic 1.7 + anthropic SDK ≥1 會把 temperature / top_p / top_k
    搬到 `extra_body`（SDK 再合併進 JSON body），兩處都算「送出」。"""
    extra = payload.get("extra_body") or {}
    return {
        k: payload.get(k, extra.get(k))
        for k in ("temperature", "top_p", "top_k")
        if k in payload or k in extra
    }


@pytest.mark.parametrize(
    "model", ["claude-opus-4-7", "claude-opus-5", "claude-sonnet-5"]
)
def test_get_chat_model_omits_temperature_on_no_sampling_models(model: str):
    svc = AnthropicLLMService(api_key="sk-ant-test", model=model)
    chat_model = svc.get_chat_model(temperature=0.7)
    assert chat_model.temperature is None
    assert chat_model.top_p is None and chat_model.top_k is None
    payload = _payload(chat_model)
    assert _wire_sampling(payload) == {}
    assert payload["model"] == model


def test_get_chat_model_keeps_temperature_on_sonnet46():
    svc = AnthropicLLMService(api_key="sk-ant-test", model="claude-sonnet-4-6")
    chat_model = svc.get_chat_model(temperature=0.3)
    assert chat_model.temperature == 0.3
    assert _wire_sampling(_payload(chat_model)) == {"temperature": 0.3}


@pytest.mark.parametrize("provider", ["anthropic", "claude"])
def test_create_chat_model_omits_temperature_on_fable(provider: str):
    chat_model = ReActAgentService._create_chat_model(
        provider=provider, model="claude-fable-5-1", temperature=0.7,
    )
    assert chat_model.temperature is None
    assert _wire_sampling(_payload(chat_model)) == {}


def test_create_chat_model_keeps_temperature_on_opus46():
    chat_model = ReActAgentService._create_chat_model(
        provider="anthropic", model="claude-opus-4-6", temperature=0.4,
    )
    assert chat_model.temperature == 0.4
    assert _wire_sampling(_payload(chat_model)) == {"temperature": 0.4}


def test_create_chat_model_keeps_reasoning_effort_after_dropping_temperature():
    """#76 不可回歸 #72：丟 temperature 之餘 thinking / effort 仍照送。"""
    chat_model = ReActAgentService._create_chat_model(
        provider="anthropic", model="claude-opus-4-7",
        temperature=0.7, reasoning_effort="high",
    )
    payload = _payload(chat_model)
    assert _wire_sampling(payload) == {}
    assert payload["thinking"] == {"type": "adaptive"}
    assert payload["output_config"]["effort"] == "high"
