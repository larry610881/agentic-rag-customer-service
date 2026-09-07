import type { ExhaustionPolicy } from "@/types/billing";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Tenant {
  id: string;
  name: string;
  plan: string;
  monthly_token_limit: number | null;
  /** S-Token-Gov.2: NULL = 全部 category 計入；list = 只計入列表內的；[] = 全不計入 */
  included_categories: string[] | null;
  default_ocr_model: string;
  default_context_model: string;
  default_classification_model: string;
  // S-KB-Followup.2
  default_summary_model?: string;
  default_intent_model?: string;
  /** Issue #54 Phase E — Prompt 發布閘門（後端預設 false） */
  prompt_gate_enabled: boolean;
  /** Issue #74：用盡策略覆寫；null = 沿用方案（system_admin 才可改） */
  exhaustion_policy_override?: ExhaustionPolicy | null;
  block_message_override?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  account: string;
  password: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}
