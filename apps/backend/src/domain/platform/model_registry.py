"""Default model registry for each provider.

Used by CreateProviderSettingUseCase to populate models on first creation.
"""

DEFAULT_MODELS: dict[str, dict[str, list[dict]]] = {
    "deepseek": {
        "llm": [
            {"model_id": "deepseek-chat", "display_name": "DeepSeek V3.2", "price": "$0.28/$0.42"},
            {"model_id": "deepseek-reasoner", "display_name": "DeepSeek R1", "price": "$0.55/$2.19"},
        ],
        "embedding": [],
    },
    "openai": {
        "llm": [
            {"model_id": "gpt-5.2", "display_name": "GPT-5.2", "price": "$1.75/$14"},
            {"model_id": "gpt-5", "display_name": "GPT-5", "price": "$1.25/$10"},
            {"model_id": "gpt-5-mini", "display_name": "GPT-5 Mini", "price": "$0.25/$2"},
            {"model_id": "gpt-5-nano", "display_name": "GPT-5 Nano", "price": "$0.05/$0.40"},
            {"model_id": "gpt-4.1", "display_name": "GPT-4.1", "price": "$2/$8"},
            {"model_id": "gpt-4.1-mini", "display_name": "GPT-4.1 Mini", "price": "$0.40/$1.60"},
            {"model_id": "gpt-4.1-nano", "display_name": "GPT-4.1 Nano", "price": "$0.10/$0.40"},
            {"model_id": "o3", "display_name": "o3", "price": "$2/$8"},
            {"model_id": "o4-mini", "display_name": "o4 Mini", "price": "$1.10/$4.40"},
        ],
        "embedding": [
            {"model_id": "text-embedding-3-small", "display_name": "Embedding 3 Small", "price": "$0.02"},
            {"model_id": "text-embedding-3-large", "display_name": "Embedding 3 Large", "price": "$0.13"},
        ],
    },
    "google": {
        "llm": [
            {"model_id": "gemini-2.5-flash", "display_name": "Gemini 2.5 Flash", "price": "$0.30/$2.50"},
            {"model_id": "gemini-2.5-flash-lite", "display_name": "Gemini 2.5 Flash Lite", "price": "$0.10/$0.40"},
            {"model_id": "gemini-2.5-pro", "display_name": "Gemini 2.5 Pro", "price": "$1.25/$10"},
        ],
        "embedding": [
            {"model_id": "gemini-embedding-001", "display_name": "Gemini Embedding", "price": "$0.15"},
            {"model_id": "text-embedding-004", "display_name": "Text Embedding 004", "price": "Free"},
        ],
    },
    "anthropic": {
        "llm": [
            {"model_id": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6", "price": "$3/$15"},
            {"model_id": "claude-haiku-4-5", "display_name": "Claude Haiku 4.5", "price": "$1/$5"},
            {"model_id": "claude-opus-4-6", "display_name": "Claude Opus 4.6", "price": "$15/$75"},
        ],
        "embedding": [],
    },
}
