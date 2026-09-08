"""Google（Gemini）原生 ChatModel —— 工具場景專用（Issue #84）。

**為什麼不能沿用 OpenAI 相容端點**：Gemini 在工具回合會回一個 ``thought_signature``，
後續把 assistant 訊息（含 functionCall）送回去時必須原樣帶上，否則回 400
``INVALID_ARGUMENT``。而 ``langchain-openai`` 雙向都會剝掉它——收訊息時
``_convert_dict_to_message`` 的 assistant 分支只留 function_call / tool_calls / audio，
送出時 tool_call 又被過濾成只剩 ``{"id", "type", "function"}``。塞 additional_kwargs
也救不回來，所以只能改用原生 SDK，由 ``langchain-google-genai`` 自己處理簽章往返。

**刻意只在綁工具時切換**：沒有工具的路徑（kb 模式）維持走 OpenAI 相容端點。
一來那條路本來就沒問題，二來 2026-09-08 的評測基準是在該路徑上量的，
整條換掉會讓既有的 Gemini 數據失去可比性。切換點在
``ReActAgentService._resolve_llm_model(..., with_tools=True)``。

推理強度對應：原生 SDK 用 ``thinking_budget``（token 預算）而不是 ``reasoning_effort``。
``none`` → 0（關閉思考），其餘強度不指定、交給模型預設——與 OpenAI 相容路徑
只放行 none 的行為一致，避免同一個 bot 換路徑就換行為。
"""

from __future__ import annotations

from typing import Any

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

GOOGLE_PROVIDERS = frozenset({"google", "gemini"})

# 只有 none 明確對應到「關閉思考」；low/medium/high 不指定預算，走模型預設。
_THINKING_BUDGET = {"none": 0, "minimal": 0}


def is_google_provider(provider_name: str | None) -> bool:
    return (provider_name or "").strip().lower() in GOOGLE_PROVIDERS


def build_google_chat_model(
    *,
    model: str,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    reasoning_effort: str | None = None,
    request_timeout: float | None = None,
    max_retries: int = 3,
) -> Any:
    """建立可安全綁工具的 Gemini ChatModel。"""
    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs: dict[str, Any] = {
        "model": model or "gemini-3.8-flash",
        "api_key": api_key,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "max_retries": max_retries,
    }
    if request_timeout:
        kwargs["request_timeout"] = request_timeout

    budget = _THINKING_BUDGET.get((reasoning_effort or "").strip().lower())
    if budget is not None:
        kwargs["thinking_budget"] = budget

    logger.info(
        "llm.google.native_chat_model",
        model=kwargs["model"],
        thinking_budget=kwargs.get("thinking_budget", "provider_default"),
        reason="tools_bound",
    )
    return ChatGoogleGenerativeAI(**kwargs)
