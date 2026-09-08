"""供應商的工具呼叫（function calling）支援能力。

2026-09-08 線上實證（Issue #84）：Google 走 OpenAI 相容端點時，工具回合會回一個
``thought_signature``，後續把 assistant 訊息（含 functionCall）送回去時必須原樣
帶上，否則回 400 ``INVALID_ARGUMENT``。而 ``langchain-openai`` **雙向都會剝掉**它：

- 收：``_convert_dict_to_message`` 的 assistant 分支只留
  function_call / tool_calls / audio
- 送：tool_call 被過濾成只剩 ``{"id", "type", "function"}``

所以塞進 ``additional_kwargs`` 也救不回來。在改用 Google 原生 SDK 或自訂訊息轉換之前，
Google 供應商 **不能** 綁工具——只要模型決定呼叫任何工具，該輪對話必定 500。

為什麼是「擋下」而不是「靜默拿掉工具」：``rag_query`` 本身就是工具，拿掉等於整個
知識庫檢索消失，模型會在沒有任何依據的情況下作答。那比報錯更危險。
"""

from __future__ import annotations

# Issue #84 已以原生 SDK 修復（google_chat_model.py），清單目前為空。
# 未來若再遇到不支援工具的供應商，加進來即可自動擋在存檔階段。
TOOL_UNSUPPORTED_PROVIDERS: frozenset[str] = frozenset()

TOOL_UNSUPPORTED_REASON = (
    "Google 供應商目前不支援工具模式（Gemini 的 OpenAI 相容端點要求回送 "
    "thought_signature，現行 LangChain 轉換會將其剝除，導致工具呼叫後必定失敗）。"
    "請改用其他供應商，或把 bot 模式設為「知識庫問答」（不使用工具）。"
)


def provider_supports_tools(provider_name: str | None) -> bool:
    """該供應商能不能綁工具。"""
    return (provider_name or "").strip().lower() not in TOOL_UNSUPPORTED_PROVIDERS
