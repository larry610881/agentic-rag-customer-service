export type ExecutionNodeType =
  | "user_input"
  | "router"
  | "meta_router"
  | "supervisor_dispatch"
  | "agent_llm"
  | "tool_call"
  | "tool_result"
  | "final_response"
  | "worker_execution";

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
  metadata: Record<string, unknown>;
};

export type AgentExecutionTrace = {
  id: string;
  trace_id: string;
  tenant_id: string;
  message_id: string | null;
  conversation_id: string | null;
  agent_mode: "react" | "supervisor" | "meta_supervisor";
  nodes: ExecutionNode[];
  total_ms: number;
  total_tokens: {
    input_tokens?: number;
    output_tokens?: number;
    estimated_cost?: number;
  } | null;
  created_at: string;
};

export type PaginatedAgentTraces = {
  total: number;
  items: AgentExecutionTrace[];
};
