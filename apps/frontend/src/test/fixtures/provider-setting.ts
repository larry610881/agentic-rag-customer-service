import type { ProviderSetting } from "@/types/provider-setting";

export const mockProviderSettings: ProviderSetting[] = [
  {
    id: "ps-001",
    provider_type: "llm",
    provider_name: "openai",
    display_name: "OpenAI GPT-4o",
    is_enabled: true,
    has_api_key: true,
    base_url: "https://api.openai.com/v1",
    models: [
      {
        model_id: "gpt-4o",
        display_name: "GPT-4o",
        is_default: true,
        is_enabled: true,
        price: "$2.50/$10",
        description: "Most capable GPT-4 model",
      },
    ],
    extra_config: {},
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

export const mockProviderSetting = mockProviderSettings[0];
