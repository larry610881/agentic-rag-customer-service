export interface IntentRoute {
  name: string;
  description: string;
  system_prompt: string;
}

/** Issue #43 — Bot-level RAG retrieval mode */
export type RetrievalMode = "raw" | "rewrite" | "hyde";

export const RETRIEVAL_MODES: RetrievalMode[] = ["raw", "rewrite", "hyde"];

/**
 * Per-tool RAG 參數覆蓋。
 * 欄位省略 / undefined 代表繼承上層（Bot per-tool → Bot 全域 default）。
 * API 序列化時應省略 undefined 欄位（JSON.stringify 會自動處理）。
 */
export interface ToolRagConfig {
  rag_top_k?: number;
  rag_score_threshold?: number;
  rerank_enabled?: boolean;
  rerank_model?: string;
  rerank_top_n?: number;
}

export interface McpToolMeta {
  name: string;
  description: string;
}

export interface McpServerConfig {
  url: string;
  name: string;
  enabled_tools: string[];
  tools: McpToolMeta[];
  version: string;
  transport?: "http" | "stdio";
  command?: string;
  args?: string[];
}

export interface Bot {
  id: string;
  short_code: string;
  tenant_id: string;
  name: string;
  description: string;
  is_active: boolean;
  bot_prompt: string;
  knowledge_base_ids: string[];
  temperature: number;
  max_tokens: number;
  history_limit: number;
  frequency_penalty: number;
  reasoning_effort: "low" | "medium" | "high";
  rag_top_k: number;
  rag_score_threshold: number;
  enabled_tools: string[];
  llm_provider: string;
  llm_model: string;
  show_sources: boolean;
  eval_provider: string;
  eval_model: string;
  eval_depth: string;
  mcp_servers: McpServerConfig[];
  max_tool_calls: number;
  base_prompt: string;
  fab_icon_url: string;
  widget_enabled: boolean;
  widget_allowed_origins: string[];
  widget_keep_history: boolean;
  widget_welcome_message: string;
  widget_placeholder_text: string;
  widget_greeting_messages: string[];
  widget_greeting_animation: "fade" | "slide" | "typewriter";
  rerank_enabled: boolean;
  rerank_model: string;
  rerank_top_n: number;
  /** Issue #43 — Bot-level RAG retrieval modes */
  rag_retrieval_modes: RetrievalMode[];
  query_rewrite_enabled: boolean;
  query_rewrite_model: string;
  query_rewrite_extra_hint: string;
  hyde_enabled: boolean;
  hyde_model: string;
  hyde_extra_hint: string;
  intent_routes: IntentRoute[];
  router_model: string;
  summary_model?: string;
  busy_reply_message: string;
  line_channel_secret: string | null;
  line_channel_access_token: string | null;
  line_show_sources: boolean;
  tool_configs?: Record<string, ToolRagConfig>;
  /** 轉接真人客服按鈕的 URL（transfer_to_human_agent tool 用；空字串 = 未設定） */
  customer_service_url?: string;
  created_at: string;
  updated_at: string;
}

export interface CreateBotRequest {
  name: string;
  description?: string;
  knowledge_base_ids?: string[];
  bot_prompt?: string;
  is_active?: boolean;
  temperature?: number;
  max_tokens?: number;
  history_limit?: number;
  frequency_penalty?: number;
  reasoning_effort?: "low" | "medium" | "high";
  rag_top_k?: number;
  rag_score_threshold?: number;
  enabled_tools?: string[];
  llm_provider?: string;
  llm_model?: string;
  show_sources?: boolean;
  eval_provider?: string;
  eval_model?: string;
  eval_depth?: "off" | "L1" | "L1+L2" | "L1+L2+L3";
  mcp_servers?: McpServerConfig[];
  max_tool_calls?: number;
  base_prompt?: string;
  widget_enabled?: boolean;
  widget_allowed_origins?: string[];
  widget_keep_history?: boolean;
  widget_welcome_message?: string;
  widget_placeholder_text?: string;
  widget_greeting_messages?: string[];
  widget_greeting_animation?: "fade" | "slide" | "typewriter";
  rerank_enabled?: boolean;
  rerank_model?: string;
  rerank_top_n?: number;
  /** Issue #43 — Bot-level RAG retrieval modes */
  rag_retrieval_modes?: RetrievalMode[];
  query_rewrite_enabled?: boolean;
  query_rewrite_model?: string;
  query_rewrite_extra_hint?: string;
  hyde_enabled?: boolean;
  hyde_model?: string;
  hyde_extra_hint?: string;
  intent_routes?: IntentRoute[];
  router_model?: string;
  summary_model?: string;
  busy_reply_message?: string;
  line_channel_secret?: string | null;
  line_channel_access_token?: string | null;
  line_show_sources?: boolean;
  tool_configs?: Record<string, ToolRagConfig>;
  customer_service_url?: string;
}

export interface UpdateBotRequest {
  name?: string;
  description?: string;
  knowledge_base_ids?: string[];
  bot_prompt?: string;
  is_active?: boolean;
  temperature?: number;
  max_tokens?: number;
  history_limit?: number;
  frequency_penalty?: number;
  reasoning_effort?: "low" | "medium" | "high";
  rag_top_k?: number;
  rag_score_threshold?: number;
  enabled_tools?: string[];
  llm_provider?: string;
  llm_model?: string;
  show_sources?: boolean;
  eval_provider?: string;
  eval_model?: string;
  eval_depth?: "off" | "L1" | "L1+L2" | "L1+L2+L3";
  mcp_servers?: McpServerConfig[];
  max_tool_calls?: number;
  base_prompt?: string;
  widget_enabled?: boolean;
  widget_allowed_origins?: string[];
  widget_keep_history?: boolean;
  widget_welcome_message?: string;
  widget_placeholder_text?: string;
  widget_greeting_messages?: string[];
  widget_greeting_animation?: "fade" | "slide" | "typewriter";
  rerank_enabled?: boolean;
  rerank_model?: string;
  rerank_top_n?: number;
  /** Issue #43 — Bot-level RAG retrieval modes */
  rag_retrieval_modes?: RetrievalMode[];
  query_rewrite_enabled?: boolean;
  query_rewrite_model?: string;
  query_rewrite_extra_hint?: string;
  hyde_enabled?: boolean;
  hyde_model?: string;
  hyde_extra_hint?: string;
  intent_routes?: IntentRoute[];
  router_model?: string;
  summary_model?: string;
  busy_reply_message?: string;
  line_channel_secret?: string | null;
  line_channel_access_token?: string | null;
  line_show_sources?: boolean;
  tool_configs?: Record<string, ToolRagConfig>;
  customer_service_url?: string;
}
