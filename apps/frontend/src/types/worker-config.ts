export type WorkerConfig = {
  id: string;
  bot_id: string;
  name: string;
  description: string;
  system_prompt: string;
  llm_provider: string | null;
  llm_model: string | null;
  temperature: number;
  max_tokens: number;
  max_tool_calls: number;
  enabled_mcp_ids: string[];
  use_rag: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
};

export type CreateWorkerRequest = {
  name: string;
  description?: string;
  system_prompt?: string;
  llm_provider?: string | null;
  llm_model?: string | null;
  temperature?: number;
  max_tokens?: number;
  max_tool_calls?: number;
  enabled_mcp_ids?: string[];
  use_rag?: boolean;
  sort_order?: number;
};

export type UpdateWorkerRequest = Partial<CreateWorkerRequest>;
