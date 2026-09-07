export interface ModelPricing {
  id: string;
  provider: string;
  model_id: string;
  display_name: string;
  category: string;
  input_price: number;
  output_price: number;
  cache_read_price: number;
  cache_creation_price: number;
  /** Issue #74：每千 token 點數；null = 用平台匯率（usd_per_point）換算 */
  points_per_1k_input?: number | null;
  points_per_1k_output?: number | null;
  effective_from: string;
  effective_to: string | null;
  created_by: string;
  created_at: string;
  note: string | null;
}

export interface CreatePricingRequest {
  provider: string;
  model_id: string;
  display_name: string;
  category: "llm" | "embedding";
  input_price: number;
  output_price: number;
  cache_read_price: number;
  cache_creation_price: number;
  /** Issue #74：留空（null）則用平台匯率換算 */
  points_per_1k_input?: number | null;
  points_per_1k_output?: number | null;
  effective_from: string;
  note: string;
}

/** Issue #74 — PUT /admin/pricing/{id}：兩欄同時給值或同時 null（清除），否則 422 */
export interface UpdatePricingPointsRequest {
  points_per_1k_input: number | null;
  points_per_1k_output: number | null;
}

export interface DryRunRecalcRequest {
  pricing_id: string;
  recalc_from: string;
  recalc_to: string;
}

export interface DryRunRecalcResult {
  dry_run_token: string;
  pricing_id: string;
  affected_rows: number;
  cost_before_total: number;
  cost_after_total: number;
  cost_delta: number;
  recalc_from: string;
  recalc_to: string;
}

export interface ExecuteRecalcRequest {
  dry_run_token: string;
  reason: string;
}

export interface ExecuteRecalcResult {
  audit_id: string;
  affected_rows: number;
  cost_before_total: number;
  cost_after_total: number;
}

export interface PricingRecalcAudit {
  id: string;
  pricing_id: string;
  recalc_from: string;
  recalc_to: string;
  affected_rows: number;
  cost_before_total: number;
  cost_after_total: number;
  cost_delta: number;
  executed_by: string;
  executed_at: string;
  reason: string;
}
