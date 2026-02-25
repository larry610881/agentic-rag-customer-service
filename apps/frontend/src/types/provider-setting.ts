export interface ModelConfig {
  model_id: string;
  display_name: string;
  is_default: boolean;
}

export interface ProviderSetting {
  id: string;
  provider_type: "llm" | "embedding";
  provider_name: string;
  display_name: string;
  is_enabled: boolean;
  has_api_key: boolean;
  base_url: string;
  models: ModelConfig[];
  extra_config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateProviderSettingRequest {
  provider_type: string;
  provider_name: string;
  display_name: string;
  api_key: string;
  base_url?: string;
  models?: ModelConfig[];
  extra_config?: Record<string, unknown>;
}

export interface UpdateProviderSettingRequest {
  display_name?: string;
  is_enabled?: boolean;
  api_key?: string;
  base_url?: string;
  models?: ModelConfig[];
  extra_config?: Record<string, unknown>;
}

export interface ConnectionResult {
  success: boolean;
  latency_ms: number;
  error: string;
}

export const PROVIDER_NAMES = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "qwen", label: "Qwen" },
  { value: "google", label: "Google" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "fake", label: "Fake (Dev)" },
] as const;

export const PROVIDER_TYPES = [
  { value: "llm", label: "LLM" },
  { value: "embedding", label: "Embedding" },
] as const;
