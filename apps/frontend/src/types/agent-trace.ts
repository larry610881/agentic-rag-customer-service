export type ExecutionNodeType =
  | "user_input"
  | "router"
  | "meta_router"
  | "supervisor_dispatch"
  | "worker_routing"
  | "agent_llm"
  | "tool_call"
  | "tool_result"
  | "final_response"
  | "worker_execution"
  // Sprint A++: Prompt guard 攔截節點（outcome=failed 會走紅色 variant）
  | "guard_input_blocked"
  | "guard_output_blocked";

export type ExecutionNode = {
  node_id: string;
  node_type: ExecutionNodeType;
  label: string;
  parent_id: string | null;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  token_usage: {
    model?: string;
    input_tokens?: number;
    output_tokens?: number;
    estimated_cost?: number;
  } | null;
  /** Phase 1: 失敗節點視覺化 source of truth；
   *  outcome=="failed" 時 metadata.error_message 應為字串。
   *  舊 trace 沒此欄位時 fallback 為 "success"。 */
  outcome?: "success" | "failed" | "partial";
  metadata: Record<string, unknown>;
};

export type TraceOutcome = "success" | "failed" | "partial";

export type AgentExecutionTrace = {
  id: string;
  trace_id: string;
  tenant_id: string;
  message_id: string | null;
  conversation_id: string | null;
  agent_mode: "react" | "supervisor" | "meta_supervisor";
  source: string;
  llm_model: string;
  llm_provider: string;
  bot_id: string | null;
  nodes: ExecutionNode[];
  total_ms: number;
  total_tokens: {
    input_tokens?: number;
    output_tokens?: number;
    total?: number;
    estimated_cost?: number;
  } | null;
  /** S-Gov.6a: snapshot trace-level outcome */
  outcome?: TraceOutcome | null;
  created_at: string;
};

export type PaginatedAgentTraces = {
  total: number;
  /** S-Gov.6a: false = flat items, true = grouped by conversation */
  grouped: boolean;
  items: AgentExecutionTrace[];
};

/** S-Gov.6a: grouped 模式下每個 group 結構
 *  S-KB-Followup.1 Lv1: 加 message preview + summary 欄位（Optional — 舊對話可能無）
 */
export type ConversationTraceGroup = {
  conversation_id: string;
  trace_count: number;
  first_at: string;
  last_at: string;
  traces: AgentExecutionTrace[];
  /** 使用者第一句訊息（截 200 字）*/
  first_user_message?: string | null;
  /** Bot 最後一次回覆（截 200 字）*/
  last_assistant_answer?: string | null;
  /** LLM-generated conversation summary（若已跑）*/
  summary?: string | null;
};

export type GroupedAgentTraces = {
  total: number;
  grouped: true;
  items: ConversationTraceGroup[];
};
