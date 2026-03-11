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

export interface DiagnosticHint {
  category: "data_source" | "rag_strategy" | "prompt" | "agent";
  severity: "critical" | "warning" | "info";
  dimension: string;
  message: string;
  suggestion: string;
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
  diagnostic_hints?: DiagnosticHint[] | null;
}

export interface PaginatedTraces {
  total: number;
  items: RAGTrace[];
}

export interface PaginatedEvals {
  total: number;
  items: EvalResult[];
}

// --- Diagnostic Rules Config ---

export interface DiagnosticSingleRule {
  dimension: string;
  threshold: number;
  category: "data_source" | "rag_strategy" | "prompt" | "agent";
  severity: "critical" | "warning" | "info";
  message: string;
  suggestion: string;
}

export interface DiagnosticComboRule {
  dim_a: string;
  op_a: string;
  threshold_a: number;
  dim_b: string;
  op_b: string;
  threshold_b: number;
  category: "data_source" | "rag_strategy" | "prompt" | "agent";
  severity: "critical" | "warning" | "info";
  dimension: string;
  message: string;
  suggestion: string;
}

export interface DiagnosticRulesConfig {
  id: string;
  single_rules: DiagnosticSingleRule[];
  combo_rules: DiagnosticComboRule[];
  updated_at: string;
}
