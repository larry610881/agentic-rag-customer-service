export interface McpServerConfig {
  url: string;
  name: string;
  enabled_tools: string[];
}

export interface Bot {
  id: string;
  short_code: string;
  tenant_id: string;
  name: string;
  description: string;
  is_active: boolean;
  system_prompt: string;
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
  agent_mode: "router" | "react";
  audit_mode: "off" | "minimal" | "full";
  eval_provider: string;
  eval_model: string;
  eval_depth: "off" | "L1" | "L1+L2" | "L1+L2+L3";
  mcp_servers: McpServerConfig[];
  max_tool_calls: number;
  line_channel_secret: string | null;
  line_channel_access_token: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateBotRequest {
  name: string;
  description?: string;
  knowledge_base_ids?: string[];
  system_prompt?: string;
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
  agent_mode?: "router" | "react";
  audit_mode?: "off" | "minimal" | "full";
  eval_provider?: string;
  eval_model?: string;
  eval_depth?: "off" | "L1" | "L1+L2" | "L1+L2+L3";
  mcp_servers?: McpServerConfig[];
  max_tool_calls?: number;
  line_channel_secret?: string | null;
  line_channel_access_token?: string | null;
}

export interface UpdateBotRequest {
  name?: string;
  description?: string;
  knowledge_base_ids?: string[];
  system_prompt?: string;
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
  agent_mode?: "router" | "react";
  audit_mode?: "off" | "minimal" | "full";
  eval_provider?: string;
  eval_model?: string;
  eval_depth?: "off" | "L1" | "L1+L2" | "L1+L2+L3";
  mcp_servers?: McpServerConfig[];
  max_tool_calls?: number;
  line_channel_secret?: string | null;
  line_channel_access_token?: string | null;
}
