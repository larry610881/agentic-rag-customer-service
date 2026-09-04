export interface IntentRoute {
  name: string;
  description: string;
  system_prompt: string;
}

/** Issue #43 — Bot-level RAG retrieval mode */
export type RetrievalMode = "raw" | "rewrite" | "hyde";

export const RETRIEVAL_MODES: RetrievalMode[] = ["raw", "rewrite", "hyde"];

/**
 * Issue #66 / #70 — Bot 推理模式。
 * fast：常見問題直答（快速道），升級推理時工具最多 2 次，rerank / 查詢改寫 / HyDE 自動關閉。
 * deep：完整多步推理，可用全部工具與 rerank。
 * kb：知識庫問答（檢索 → 單次生成），不用工具、不升級；未命中回固定話術。
 */
export type BotMode = "fast" | "deep" | "kb";

export const BOT_MODES: BotMode[] = ["fast", "deep", "kb"];

/**
 * Issue #70 — 回覆輸出格式。
 * text：一般（保留 Markdown）；plain_text：自動移除 Markdown 符號；json：結構化輸出（可附 schema）。
 */
export type OutputFormat = "text" | "plain_text" | "json";

export const OUTPUT_FORMATS: OutputFormat[] = ["text", "plain_text", "json"];

/** Issue #70 — output_format=json 時的 JSON schema（任意 JSON 物件） */
export type BotOutputSchema = Record<string, unknown>;

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
  /** Per-tool KB binding — 覆寫 Bot 全域 knowledge_base_ids；空 list 視為未覆寫 */
  kb_ids?: string[];
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
  /** Issue #54 — 發布閘門設定（治理欄位，不受版控） */
  gate_mode: "off" | "warn" | "block";
  gate_soft_threshold: number;
  gate_repeats: number;
  gate_auto_publish: boolean;
  gate_daily_limit: number;
  gate_budget_usd: number;
  gate_excluded_cases: string[];
  /** Issue #66 / #70 — 推理模式（fast = 快速道 / deep = 深度道 / kb = 知識庫問答） */
  mode: BotMode;
  /** Issue #70 — 輸出格式（預設 text） */
  output_format?: OutputFormat;
  /** Issue #70 — JSON schema；僅 output_format=json 時有意義 */
  output_schema?: BotOutputSchema | null;
  /** Issue #70 — 未命中話術；空字串 = 平台預設文案 */
  miss_reply?: string;
  /** Issue #70 — JSON 輸出時純文字通路顯示的欄位（預設 answer） */
  output_text_field?: string;
  /** 長期記憶開關 */
  memory_enabled?: boolean;
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
  /** Issue #54 — 發布閘門設定 */
  gate_mode?: "off" | "warn" | "block";
  gate_soft_threshold?: number;
  gate_repeats?: number;
  gate_auto_publish?: boolean;
  gate_daily_limit?: number;
  gate_budget_usd?: number;
  gate_excluded_cases?: string[];
  /** Issue #66 / #70 — 推理模式（fast = 快速道 / deep = 深度道 / kb = 知識庫問答） */
  mode?: BotMode;
  /** Issue #70 — 輸出格式 */
  output_format?: OutputFormat;
  /** Issue #70 — JSON schema；僅 output_format=json 時有意義 */
  output_schema?: BotOutputSchema | null;
  /** Issue #70 — 未命中話術；空字串 = 平台預設文案 */
  miss_reply?: string;
  /** Issue #70 — JSON 輸出時純文字通路顯示的欄位（預設 answer） */
  output_text_field?: string;
  /** 長期記憶開關 */
  memory_enabled?: boolean;
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
  /** Issue #54 — 發布閘門設定 */
  gate_mode?: "off" | "warn" | "block";
  gate_soft_threshold?: number;
  gate_repeats?: number;
  gate_auto_publish?: boolean;
  gate_daily_limit?: number;
  gate_budget_usd?: number;
  gate_excluded_cases?: string[];
  /** Issue #66 / #70 — 推理模式（fast = 快速道 / deep = 深度道 / kb = 知識庫問答） */
  mode?: BotMode;
  /** Issue #70 — 輸出格式 */
  output_format?: OutputFormat;
  /** Issue #70 — JSON schema；僅 output_format=json 時有意義 */
  output_schema?: BotOutputSchema | null;
  /** Issue #70 — 未命中話術；空字串 = 平台預設文案 */
  miss_reply?: string;
  /** Issue #70 — JSON 輸出時純文字通路顯示的欄位（預設 answer） */
  output_text_field?: string;
  /** 長期記憶開關 */
  memory_enabled?: boolean;
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
