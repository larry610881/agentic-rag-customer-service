"""HyDE (Hypothetical Document Embeddings) generator — RAG 檢索共用 helper.

Issue #43 Stage 2.2

設計
----
HyDE = 用 LLM 先「假裝回答」使用者問題，再用假答案做向量檢索。
理論基礎：問題向量跟答案向量在 embedding 空間距離較遠（Q vs A），
而假答案跟真答案的內容更接近 → 假答案 → 檢索的相關性常常更好。

兩種 caller 共用：
1. Real RAG (``query_rag_use_case``) — 多 mode 之一
2. Retrieval Playground (``test_retrieval_use_case``) — 套用同樣 helper

Bot context
-----------
若有 ``bot_system_prompt``：用 PromptBlock 結構，bot 自己 prompt 作 SYSTEM block，
最小化 hyde 指令 USER block → 真實對齊「該 bot 在那角色下會怎麼回答」
避免額外指令污染 bot persona。

Extra hint
----------
``extra_hint`` 提供 fine-tune 機會（例：「答案應提到具體分店名稱」），
若有則附加到指令中。
"""

from __future__ import annotations

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


# 通用 HyDE prompt（沒指定 bot 時用）
_GENERIC_HYDE_PROMPT = (
    "你是 RAG 檢索助手。為了找到相關文件，請先「假裝回答」以下問題。\n"
    "不需要真的回答正確 — 寫一段「合理且具體的答案」即可，"
    "目的是讓向量檢索能匹配真正的知識文件。\n"
    "\n"
    "規則：\n"
    "- 100-200 字的答案段落\n"
    "- 包含問題涉及的關鍵詞、產品名、政策名等專有名詞\n"
    "- 用陳述句寫成像「答案」而非「問題」\n"
    "- 保持中文，不要翻譯\n"
    "- 直接輸出答案內容，不要解釋、不要前綴、不要引號\n"
    "{extra_hint}"
    "\n"
    "問題：{query}\n"
    "\n"
    "假設答案："
)

# Bot-aware HyDE — 用 bot 自己的 system_prompt 作 SYSTEM block
# 跟真實對話對齊：bot LLM 想像「我會怎麼回答這問題」的草稿
_BOT_HYDE_INSTRUCTION = (
    "使用者問你：「{query}」\n"
    "\n"
    "假設你已經知道答案，請寫一段 100-200 字的「合理答案草稿」，"
    "用你的身分與領域用語回答。寫法要像答案、不要像問題。"
    "目的是供 RAG 檢索使用，所以答案要包含具體的產品名、政策名、流程名等關鍵詞。\n"
    "{extra_hint}"
    "\n"
    "只輸出答案內容，不要解釋、不要引號、不要前綴。"
)


def _format_extra_hint(extra_hint: str) -> str:
    if not extra_hint or not extra_hint.strip():
        return ""
    return f"- 額外提示：{extra_hint.strip()}\n"


async def generate_hyde(
    raw_query: str,
    model: str = "",
    bot_system_prompt: str = "",
    extra_hint: str = "",
    api_key_resolver=None,
) -> str:
    """Generate hypothetical answer for HyDE retrieval.

    Args:
        raw_query: 使用者原始問題
        model: LLM model spec ("provider:model_id")，空字串走預設 haiku
        bot_system_prompt: 若有，用 bot prompt 作 SYSTEM block 對齊真實對話
        extra_hint: 額外提示詞（fine-tune），例：「答案應提到分店」
        api_key_resolver: async (provider_name) -> api_key

    Returns:
        假設答案字串；任何錯誤 fallback 回原 query（不擋下游 search）
    """
    from src.domain.llm.prompt_block import BlockRole, PromptBlock
    from src.infrastructure.llm.llm_caller import call_llm

    spec = model or "anthropic:claude-haiku-4-5"
    extra_hint_text = _format_extra_hint(extra_hint)
    try:
        if bot_system_prompt:
            blocks = [
                PromptBlock(
                    text=bot_system_prompt,
                    role=BlockRole.SYSTEM,
                ),
                PromptBlock(
                    text=_BOT_HYDE_INSTRUCTION.format(
                        query=raw_query,
                        extra_hint=extra_hint_text,
                    ),
                    role=BlockRole.USER,
                ),
            ]
            result = await call_llm(
                model_spec=spec,
                prompt=blocks,
                max_tokens=400,
                api_key_resolver=api_key_resolver,
            )
        else:
            prompt = _GENERIC_HYDE_PROMPT.format(
                query=raw_query,
                extra_hint=extra_hint_text,
            )
            result = await call_llm(
                model_spec=spec,
                prompt=prompt,
                max_tokens=400,
                api_key_resolver=api_key_resolver,
            )
        answer = result.text.strip().strip('"').strip("「").strip("」")
        return answer or raw_query
    except Exception:
        logger.warning("rag.hyde_failed", exc_info=True)
        return raw_query
