"""LLM domain abstractions — provider-agnostic prompt structure.

S-LLM-Cache.1: 為 cross-provider prompt caching 提供統一的 PromptBlock 抽象。
Caller 用 PromptBlock list 表達 prompt 結構與 cache hint，由 infrastructure
adapter (Anthropic / OpenAI-compatible) 翻譯成各家 API 對應形式。
"""

from src.domain.llm.prompt_block import BlockRole, CacheHint, PromptBlock

__all__ = ["BlockRole", "CacheHint", "PromptBlock"]
