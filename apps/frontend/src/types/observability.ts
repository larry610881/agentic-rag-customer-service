export interface RAGTraceStep {
  /** tool_name from agent tool_calls, or legacy "name" */
  tool_name?: string;
  name?: string;
  reasoning?: string;
  elapsed_ms?: number;
  iteration?: number;
  tool_input?: Record<string, unknown>;
  tool_output?: string;
  metadata?: Record<string, unknown>;
}

export interface RAGTrace {
  id: string;
  trace_id: string;
  query: string;
  tenant_id: string;
  message_id: string | null;
  steps: RAGTraceStep[] | null;
  total_ms: number;
  chunk_count: number;
  prompt_snapshot?: string | null;
  created_at: string;
}

export interface ChunkScore {
  index: number;
  score: number;
  reason: string;
}

export interface EvalDimension {
  name: string;
  score: number;
  explanation: string;
  metadata?: { chunk_scores?: ChunkScore[] } | null;
}

export interface EvalResult {
  id: string;
  eval_id: string;
  message_id: string | null;
  trace_id: string | null;
  tenant_id: string;
  layer: string;
  dimensions: EvalDimension[] | null;
  avg_score: number;
  model_used: string;
  created_at: string;
}

export interface PaginatedTraces {
  total: number;
  items: RAGTrace[];
}

export interface PaginatedEvals {
  total: number;
  items: EvalResult[];
}
