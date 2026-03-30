"""Default model registry for each provider.

Used by CreateProviderSettingUseCase to populate models on first creation.

Embedding is fixed to OpenAI text-embedding-3-small (1536 dim) globally.

Pricing: input_price / output_price = USD per 1M tokens (2026-03 verified).
Cache pricing: cache_read_price / cache_creation_price = USD per 1M tokens.
  - cache_read_price: 快取命中時的 input 價格（通常為 input_price × 10%）
  - cache_creation_price: 快取建立時的額外費用（僅 Anthropic 收取，input_price × 125%）
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
}
