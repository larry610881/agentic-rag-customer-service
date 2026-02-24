import type { Bot } from "@/types/bot";

export const mockBots: Bot[] = [
  {
    id: "bot-1",
    tenant_id: "tenant-1",
    name: "Customer Service Bot",
    description: "Handles customer inquiries",
    is_active: true,
    system_prompt: "You are a helpful customer service bot.",
    knowledge_base_ids: ["kb-1", "kb-2"],
    temperature: 0.3,
    max_tokens: 1024,
    history_limit: 10,
    frequency_penalty: 0.0,
    reasoning_effort: "medium",
    line_channel_secret: null,
    line_channel_access_token: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-15T00:00:00Z",
  },
  {
    id: "bot-2",
    tenant_id: "tenant-1",
    name: "FAQ Bot",
    description: "Answers frequently asked questions",
    is_active: false,
    system_prompt: "",
    knowledge_base_ids: ["kb-1"],
    temperature: 0.5,
    max_tokens: 2048,
    history_limit: 5,
    frequency_penalty: 0.1,
    reasoning_effort: "low",
    line_channel_secret: null,
    line_channel_access_token: null,
    created_at: "2024-02-01T00:00:00Z",
    updated_at: "2024-02-10T00:00:00Z",
  },
];

export const mockBot: Bot = mockBots[0];
