/** Issue #54 — Bot 設定版本（config as commit）與閘門 run 型別 */

export type VersionStatus =
  | "draft"
  | "validating"
  | "pending_publish"
  | "published"
  | "rejected";

export type VersionSource = "manual" | "optimizer" | "rollback" | "seed";

export type GateVerdict = "pass" | "fail" | "forced" | "skipped";

export interface ConfigVersion {
  id: string;
  bot_id: string;
  version_no: number;
  status: VersionStatus;
  is_current: boolean;
  source: VersionSource;
  source_run_id: string | null;
  gate_run_id: string | null;
  gate_verdict: GateVerdict | null;
  changed_fields: string[];
  author_user_id: string | null;
  published_at: string | null;
  created_at: string;
}

export interface ConfigVersionDetail extends ConfigVersion {
  config_snapshot: Record<string, unknown>;
  snapshot_schema: number;
}

export interface GateRunAssertion {
  type: string;
  severity: "hard" | "soft";
  passed: boolean;
  message: string;
}

export interface GateRunRound {
  round: number;
  response_text: string;
  truncated: boolean;
  assertions: GateRunAssertion[];
  latency_ms: number;
  tokens: number;
  cost: number;
  trace_id: string | null;
  trace_nodes: Record<string, unknown>[] | null;
}

export interface GateRunCase {
  case_id: string;
  question: string;
  priority: string;
  rounds: GateRunRound[];
  pass_rate: number | null;
  soft_passed: boolean | null;
  hard_failed: boolean | null;
  unstable: boolean | null;
}

export interface GateRunDetails {
  type?: undefined;
  cases: GateRunCase[];
  aborted: boolean;
  excluded_platform_cases: string[];
}

/** Phase G — 真實流量回放 pairwise 對比（復用 gate run 容器） */
export interface ReplayCompareItem {
  question: string;
  baseline_answer: string;
  candidate_answer: string;
  verdict: "candidate" | "baseline" | "tie";
  judge_normal: string;
  judge_swapped: string;
  baseline_cost: number;
  candidate_cost: number;
}

export interface ReplayCompareDetails {
  type: "replay_compare";
  aborted?: boolean;
  summary?: {
    candidate_wins: number;
    baseline_wins: number;
    ties: number;
    win_rate: number;
  };
  items?: ReplayCompareItem[];
}

export interface GateRun {
  id: string;
  bot_id: string;
  version_id: string;
  status: "queued" | "running" | "completed" | "error";
  verdict: "pass" | "fail" | null;
  fail_reasons: string[];
  dataset_ids: string[];
  repeats: number;
  soft_threshold: number;
  total_cases: number | null;
  hard_failed_cases: number | null;
  soft_pass_rate: number | null;
  unstable_cases: number | null;
  est_cost: number | null;
  actual_cost: number | null;
  details: GateRunDetails | ReplayCompareDetails | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface GateEstimate {
  total_cases: number;
  p0_cases: number;
  repeats: number;
  est_calls: number;
  history_messages: number;
  cost_per_call: number;
  est_cost: number;
  dataset_ids: string[];
  has_custom_enabled: boolean;
  excluded_platform_cases: string[];
  budget_usd: number;
  within_budget: boolean;
}

export interface VersionMetrics {
  version_id: string;
  message_count: number;
  input_tokens: number;
  output_tokens: number;
  total_cost: number;
  avg_latency_ms: number | null;
  eval_avg_by_layer: Record<string, number>;
  feedback_up: number;
  feedback_down: number;
  feedback_positive_rate: number | null;
}
