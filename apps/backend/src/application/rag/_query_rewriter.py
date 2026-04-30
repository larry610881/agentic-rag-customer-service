"""Query rewriter — RAG 查詢改寫共用 helper.

兩種 caller 共用：
1. Real RAG (`query_rag_use_case`) — 計畫 Stage 2 接入
2. Retrieval Playground (`test_retrieval_use_case`) — 已接入

設計原則
--------
- 有 bot_system_prompt：用 PromptBlock 結構，bot 自己 prompt 作 SYSTEM block，
  最小化 rewrite 指令 USER block → 真實對齊「該 bot 在那角色下會怎麼搜尋」
  避免額外指令污染 bot persona
- 沒 bot：用通用 rewrite prompt 作 baseline

避免 drift
---------
之前 Playground 的 _rewrite_query 直接寫死在 test_retrieval_use_case，
若未來要把 bot 真實 RAG 也加 rewrite，會出現「Playground 跟真實 RAG
對同一 query 改寫結果不同」的詭異情況。集中於此 module 一勞永逸。
"""

from __future__ import annotations

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


# 通用 rewrite（沒指定 bot 時用）— 純 RAG 改寫示範
_GENERIC_REWRITE_PROMPT = (
    "你是 RAG 檢索查詢改寫助手。把使用者的問題改寫成適合向量檢索的查詢字串。\n"
    "\n"
    "規則：\n"
    "- 保留所有關鍵詞和專有名詞\n"
    "- 移除語氣詞（請、麻煩、想知道、可以告訴我等）\n"
    "- 必要時擴展常見同義詞\n"
    "- 保持中文，不要翻譯\n"
    "- 直接輸出改寫後字串，不要解釋、不要引號\n"
    "{extra_hint}"
    "\n"
    "使用者問題：{query}\n"
    "\n"
    "改寫後："
)

# Bot-aware rewrite — 用 bot 自己的 system_prompt 作主，最小化 rewrite 指令
# 跟真實對話對齊：bot LLM 思考「我要呼叫 rag_query 用什麼 query」的決策過程
_BOT_REWRITE_INSTRUCTION = (
    "使用者問你：「{query}」\n"
    "\n"
    "假設你決定要呼叫 RAG 知識庫檢索工具來找答案，"
    "你會用什麼查詢字串去搜尋？以你的身分與領域知識決定查詢用詞。\n"
    "{extra_hint}"
    "\n"
    "只輸出查詢字串本身，不要解釋、不要引號、不要前綴。"
)


def _format_extra_hint(extra_hint: str) -> str:
    if not extra_hint or not extra_hint.strip():
        return ""
    return f"- 額外提示：{extra_hint.strip()}\n"


async def rewrite_query(
    raw_query: str,
    model: str = "",
    bot_system_prompt: str = "",
    extra_hint: str = "",
    api_key_resolver=None,
) -> str:
    """Use LLM to rewrite query for better vector retrieval.

    Args:
        raw_query: 使用者原始問題
        model: LLM model spec ("provider:model_id")，空字串走預設 haiku
        bot_system_prompt: 若有，用 bot prompt 作 SYSTEM block 對齊真實對話
        api_key_resolver: async (provider_name) -> api_key

    Returns:
        改寫後字串；任何錯誤 fallback 回原 query（不擋下游 search）
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
                    text=_BOT_REWRITE_INSTRUCTION.format(
                        query=raw_query,
                        extra_hint=extra_hint_text,
                    ),
                    role=BlockRole.USER,
                ),
            ]
            result = await call_llm(
                model_spec=spec,
                prompt=blocks,
                max_tokens=200,
                api_key_resolver=api_key_resolver,
            )
        else:
            prompt = _GENERIC_REWRITE_PROMPT.format(
                query=raw_query,
                extra_hint=extra_hint_text,
            )
            result = await call_llm(
                model_spec=spec,
                prompt=prompt,
                max_tokens=200,
                api_key_resolver=api_key_resolver,
            )
        rewritten = result.text.strip().strip('"').strip("「").strip("」")
        return rewritten or raw_query
    except Exception:
        logger.warning("rag.query_rewrite_failed", exc_info=True)
        return raw_query
