"""Default model registry for each provider.

Used by CreateProviderSettingUseCase to populate models on first creation，
and by RecordUsageUseCase._estimate_cost_from_registry 計算 estimated_cost。

Embedding is fixed to OpenAI text-embedding-3-large (3072 dim) globally.

Pricing: input_price / output_price = USD per 1M tokens (2026-04 verified).
Cache pricing: cache_read_price / cache_creation_price = USD per 1M tokens.
  - cache_read_price: 快取命中時的 input 價格（通常為 input_price × 10%）
  - cache_creation_price: 快取建立時的額外費用（僅 Anthropic / Claude 系列收取，
    通常為 input_price × 125%。OpenAI / Gemini / DeepSeek 自動 prefix cache 無 write
    penalty → 0）

S-LLM-Cache.2 修正：
  - `litellm:azure_ai/claude-*` 的 `cache_creation_price` 之前錯設成 0，修正為跟直連
    Anthropic 同定價（Azure AI Claude 跟原生 Anthropic API 收費一致）
  - 新增 xai (Grok) / embedding 定價子分類（完整性）
"""

DEFAULT_MODELS: dict[str, dict[str, list[dict]]] = {
    "deepseek": {
        "llm": [
            {"model_id": "deepseek-chat", "display_name": "DeepSeek V3.2", "price": "$0.27/$1.10", "input_price": 0.27, "output_price": 1.10, "cache_read_price": 0.027, "cache_creation_price": 0},
            {"model_id": "deepseek-reasoner", "display_name": "DeepSeek R1", "price": "$0.55/$2.19", "input_price": 0.55, "output_price": 2.19, "cache_read_price": 0.055, "cache_creation_price": 0},
        ],
    },
    "openai": {
        "llm": [
            {"model_id": "gpt-5.2", "display_name": "GPT-5.2", "price": "$1.75/$14", "input_price": 1.75, "output_price": 14.0, "cache_read_price": 0.175, "cache_creation_price": 0},
            {"model_id": "gpt-5.1", "display_name": "GPT-5.1", "price": "$1.25/$10", "input_price": 1.25, "output_price": 10.0, "cache_read_price": 0.125, "cache_creation_price": 0},
            {"model_id": "gpt-5", "display_name": "GPT-5", "price": "$1.25/$10", "input_price": 1.25, "output_price": 10.0, "cache_read_price": 0.125, "cache_creation_price": 0},
            {"model_id": "gpt-5-mini", "display_name": "GPT-5 Mini", "price": "$0.25/$2", "input_price": 0.25, "output_price": 2.0, "cache_read_price": 0.025, "cache_creation_price": 0},
            {"model_id": "gpt-5-nano", "display_name": "GPT-5 Nano", "price": "$0.05/$0.40", "input_price": 0.05, "output_price": 0.40, "cache_read_price": 0.005, "cache_creation_price": 0},
        ],
        "embedding": [
            {"model_id": "text-embedding-3-large", "display_name": "text-embedding-3-large (3072d)", "price": "$0.13/1M", "input_price": 0.13, "output_price": 0, "cache_read_price": 0, "cache_creation_price": 0},
            {"model_id": "text-embedding-3-small", "display_name": "text-embedding-3-small (1536d)", "price": "$0.02/1M", "input_price": 0.02, "output_price": 0, "cache_read_price": 0, "cache_creation_price": 0},
        ],
    },
    "google": {
        "llm": [
            {"model_id": "gemini-3.1-pro-preview", "display_name": "Gemini 3.1 Pro", "price": "$2/$12", "input_price": 2.0, "output_price": 12.0, "cache_read_price": 0.2, "cache_creation_price": 0},
            {"model_id": "gemini-3.1-flash-lite-preview", "display_name": "Gemini 3.1 Flash Lite", "price": "$0.25/$1.50", "input_price": 0.25, "output_price": 1.50, "cache_read_price": 0.025, "cache_creation_price": 0},
            {"model_id": "gemini-3-flash-preview", "display_name": "Gemini 3 Flash", "price": "$0.50/$3", "input_price": 0.50, "output_price": 3.0, "cache_read_price": 0.05, "cache_creation_price": 0},
            {"model_id": "gemini-2.5-pro", "display_name": "Gemini 2.5 Pro", "price": "$1.25/$10", "input_price": 1.25, "output_price": 10.0, "cache_read_price": 0.125, "cache_creation_price": 0},
            {"model_id": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash", "price": "$0.30/$2.50", "input_price": 0.30, "output_price": 2.50, "cache_read_price": 0.03, "cache_creation_price": 0},
            {"model_id": "gemini-2.5-flash-lite", "display_name": "Gemini 2.5 Flash Lite", "price": "$0.10/$0.40", "input_price": 0.10, "output_price": 0.40, "cache_read_price": 0.01, "cache_creation_price": 0},
        ],
    },
    "anthropic": {
        "llm": [
            {"model_id": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6", "price": "$3/$15", "input_price": 3.0, "output_price": 15.0, "cache_read_price": 0.3, "cache_creation_price": 3.75},
            {"model_id": "claude-haiku-4-5", "display_name": "Claude Haiku 4.5", "price": "$1/$5", "input_price": 1.0, "output_price": 5.0, "cache_read_price": 0.1, "cache_creation_price": 1.25},
            {"model_id": "claude-opus-4-6", "display_name": "Claude Opus 4.6", "price": "$5/$25", "input_price": 5.0, "output_price": 25.0, "cache_read_price": 0.5, "cache_creation_price": 6.25},
        ],
    },
    "litellm": {
        # S-LLM-Cache.2: Azure AI Claude 跟直連 Anthropic 同定價，cache_creation_price
        # 不是 0（之前錯），修為 input × 1.25
        "llm": [
            {"model_id": "azure_ai/claude-opus-4-6", "display_name": "Claude Opus 4.6 (via LiteLLM)", "price": "$5/$25", "input_price": 5.0, "output_price": 25.0, "cache_read_price": 0.5, "cache_creation_price": 6.25},
            {"model_id": "azure_ai/claude-sonnet-4-5", "display_name": "Claude Sonnet 4.5 (via LiteLLM)", "price": "$3/$15", "input_price": 3.0, "output_price": 15.0, "cache_read_price": 0.3, "cache_creation_price": 3.75},
            {"model_id": "azure_ai/claude-haiku-4-5", "display_name": "Claude Haiku 4.5 (via LiteLLM)", "price": "$1/$5", "input_price": 1.0, "output_price": 5.0, "cache_read_price": 0.1, "cache_creation_price": 1.25},
        ],
    },
    # xAI Grok — 2026 起支援 prompt caching（自動 prefix，類 OpenAI 模式）
    "xai": {
        "llm": [
            {"model_id": "grok-3", "display_name": "Grok 3", "price": "$3/$15", "input_price": 3.0, "output_price": 15.0, "cache_read_price": 0.75, "cache_creation_price": 0},
            {"model_id": "grok-3-mini", "display_name": "Grok 3 Mini", "price": "$0.30/$0.50", "input_price": 0.30, "output_price": 0.50, "cache_read_price": 0.075, "cache_creation_price": 0},
        ],
    },
}
