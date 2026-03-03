export interface ProviderModelOption {
  id: string;
  name: string;
  price: string;
}

export interface ProviderModelGroup {
  llm: ProviderModelOption[];
  embedding: ProviderModelOption[];
}

/** Display labels for providers */
export const PROVIDER_LABELS: Record<string, string> = {
  deepseek: "DeepSeek",
  openai: "OpenAI",
  google: "Google Gemini",
  anthropic: "Anthropic Claude",
};

/** Pre-defined provider list order (shown on settings page) */
export const PROVIDER_ORDER = ["deepseek", "openai", "google", "anthropic"] as const;

export const PROVIDER_MODELS: Record<string, ProviderModelGroup> = {
  deepseek: {
    llm: [
      { id: "deepseek-chat", name: "DeepSeek V3", price: "$0.14/$0.28" },
      { id: "deepseek-reasoner", name: "DeepSeek R1", price: "$0.55/$2.19" },
    ],
    embedding: [],
  },
  openai: {
    llm: [
      { id: "gpt-4o", name: "GPT-4o", price: "$2.50/$10" },
      { id: "gpt-4o-mini", name: "GPT-4o Mini", price: "$0.15/$0.60" },
      { id: "gpt-4.1", name: "GPT-4.1", price: "$2.00/$8.00" },
      { id: "gpt-4.1-mini", name: "GPT-4.1 Mini", price: "$0.40/$1.60" },
      { id: "gpt-4.1-nano", name: "GPT-4.1 Nano", price: "$0.10/$0.40" },
    ],
    embedding: [
      { id: "text-embedding-3-small", name: "Embedding 3 Small", price: "$0.02" },
      { id: "text-embedding-3-large", name: "Embedding 3 Large", price: "$0.13" },
    ],
  },
  google: {
    llm: [
      { id: "gemini-2.5-flash", name: "Gemini 2.5 Flash", price: "$0.15/$0.60" },
      { id: "gemini-2.5-flash-lite", name: "Gemini 2.5 Flash Lite", price: "$0.10/$0.40" },
      { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro", price: "$1.25/$10" },
    ],
    embedding: [
      { id: "gemini-embedding-001", name: "Gemini Embedding", price: "$0.15" },
      { id: "text-embedding-004", name: "Text Embedding 004", price: "Free" },
    ],
  },
  anthropic: {
    llm: [
      { id: "claude-sonnet-4-6", name: "Claude Sonnet 4.6", price: "$3/$15" },
      { id: "claude-haiku-4-5", name: "Claude Haiku 4.5", price: "$1/$5" },
      { id: "claude-opus-4-6", name: "Claude Opus 4.6", price: "$5/$25" },
    ],
    embedding: [],
  },
};
